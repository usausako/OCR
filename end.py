from pyautogui import *
import time
import pyperclip
import cv2
import numpy as np
from PIL import ImageGrab
from paddleocr import PaddleOCR
import mysql.connector
import re
import datetime
import os

# 数据库配置信息
DB_CONFIG = {
    'host': '#',
    'user': 'root',
    'password': '#',
    'database': '#',
    'port': #
}

# 设置要检测的屏幕区域
REGION_COORDS = (1500, 0, 1920, 600)
TARGET_TEXT = "最近24小时"

# 状态文件路径
STATE_FILE = "last_processed_id.txt"
# 最大处理条数
MAX_PROCESS = 40


def 获取当天已查询的竞对id():
    """获取当天已在竞对每日统计表中的竞对ID"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        query = "SELECT DISTINCT `竞对id` FROM `竞对每日统计` WHERE `日期` = %s"
        cursor.execute(query, (current_date,))
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        # 提取竞对ID列表
        return [row[0] for row in results] if results else []
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return []


def 获取最后处理的竞对id():
    """从状态文件获取最后处理的竞对ID"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except:
                return 0
    return 0


def 保存最后处理的竞对id(jingdui_id):
    """保存最后处理的竞对ID到状态文件"""
    with open(STATE_FILE, 'w') as f:
        f.write(str(jingdui_id))


def 从数据库读取数据():
    """从 MySQL 数据库读取所有地址和店名，排除当天已查询的，并按竞对ID排序"""
    try:
        # 获取当天已查询的竞对ID
        processed_ids = 获取当天已查询的竞对id()
        # 获取最后处理的竞对ID
        last_processed_id = 获取最后处理的竞对id()

        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        if processed_ids:
            # 使用参数化查询避免SQL注入
            placeholders = ', '.join(['%s'] * len(processed_ids))
            query = f"""
                SELECT `导航地址`, `竞对名称`, `竞对id`, `门店id` 
                FROM `竞对门店档案` 
                WHERE `竞对id` > %s AND `竞对id` NOT IN ({placeholders})
                ORDER BY `竞对id` ASC
                LIMIT {MAX_PROCESS}
            """
            params = [last_processed_id] + processed_ids
            cursor.execute(query, tuple(params))
        else:
            # 如果没有已处理的数据，查询所有
            query = f"""
                SELECT `导航地址`, `竞对名称`, `竞对id`, `门店id` 
                FROM `竞对门店档案` 
                WHERE `竞对id` > %s
                ORDER BY `竞对id` ASC
                LIMIT {MAX_PROCESS}
            """
            cursor.execute(query, (last_processed_id,))

        results = cursor.fetchall()
        cursor.close()
        connection.close()
        return results
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return []


def 输入地址(dizhi):
    moveTo(1500, 100, duration=0.1)
    time.sleep(2)
    click()
    moveTo(1700, 100, duration=0.1)
    time.sleep(2)
    click()
    time.sleep(2)
    pyperclip.copy(dizhi)
    hotkey('ctrl', 'v')
    time.sleep(2)
    moveTo(1700, 185, duration=0.1)
    time.sleep(2)
    click()
    time.sleep(2)


def 输入竞对店名(dianming):
    moveTo(1500, 140, duration=0.1)
    time.sleep(0.5)
    click()
    time.sleep(2)
    pyperclip.copy(dianming)
    hotkey('ctrl', 'v')
    time.sleep(2)
    moveTo(1860, 100, duration=0.1)
    time.sleep(2)
    click()


def capture_screen_region(coords):
    """截取屏幕指定区域"""
    screen = ImageGrab.grab(bbox=coords)
    return cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)


def check_text_in_region():
    """检测指定区域是否包含目标文本"""
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    region_img = capture_screen_region(REGION_COORDS)
    result = ocr.ocr(region_img, cls=True)

    if result and result[0]:
        for line in result:
            for word_info in line:
                text = word_info[1][0]
                if TARGET_TEXT in text:
                    return 0
    return 1


def 重新搜索():
    moveTo(1700, 100, duration=0.1)
    time.sleep(2)
    click()
    moveTo(1860, 100, duration=0.1)
    time.sleep(2)
    click()
    time.sleep(2)


def 返回主页():
    moveTo(1480, 100, duration=0.1)
    time.sleep(2)
    click()
    time.sleep(2)
    click()


def extract_shop_info():
    """使用OCR提取店铺信息"""
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    full_screen = ImageGrab.grab()
    full_img = cv2.cvtColor(np.array(full_screen), cv2.COLOR_RGB2BGR)
    result = ocr.ocr(full_img, cls=True)

    shop_info = {
        '评分': '',
        '销售量': '',  # 对应数据库的"订单量"
        '配送时间': '',
        '起送费': '',
        '配送费': '',
        '距离': '',
        '24小时营业': '否',
        '店铺活动': '',
        '神券活动': '无',
        '24小时下单': ''  # 对应数据库的"24小时销量"
    }

    all_text = []
    if result and result[0]:
        for line in result:
            for word_info in line:
                text = word_info[1][0]
                all_text.append(text)

    all_text_str = ' '.join(all_text)

    # 提取评分
    rating_match = re.search(r'★(\d+\.\d+)', all_text_str)
    if rating_match:
        shop_info['评分'] = rating_match.group(1)

    # 提取销售量 (对应数据库的"订单量")
    sales_match = re.search(r'已售([\d\.]+[wW万]?)', all_text_str)
    if sales_match:
        shop_info['销售量'] = sales_match.group(1)

    # 提取配送时间
    delivery_time_match = re.search(r'(\d+)分钟', all_text_str)
    if delivery_time_match:
        shop_info['配送时间'] = delivery_time_match.group(1) + '分钟'

    # 提取起送费和配送费
    start_fee_match = re.search(r'起送￥(\d+)', all_text_str)
    delivery_fee_match = re.search(r'配送约￥(\d+)', all_text_str)
    if start_fee_match:
        shop_info['起送费'] = start_fee_match.group(1)
    if delivery_fee_match:
        shop_info['配送费'] = delivery_fee_match.group(1)

    # 提取距离
    distance_match_km = re.search(r'(\d+\.\d+)km', all_text_str)
    distance_match_m = re.search(r'(\d+)m', all_text_str)
    if distance_match_km:
        shop_info['距离'] = distance_match_km.group(1) + 'km'
    elif distance_match_m:
        shop_info['距离'] = distance_match_m.group(1) + 'm'

    # 判断24小时营业
    if '24小时营业' in all_text_str:
        shop_info['24小时营业'] = '是'

    # 判断店铺活动
    if re.search(r'\d+减\d+', all_text_str):
        shop_info['店铺活动'] = '有店铺活动'

    # 判断神券活动
    if re.search(r'神券(?!.*(无|领取完毕))', all_text_str):
        shop_info['神券活动'] = '有'

    # 提取24小时下单 (对应数据库的"24小时销量")
    recent_24h_text = next((text for text in all_text if '最近24小时' in text), '')
    if recent_24h_text:
        match = re.search(r'最近24小时(\d+)人下单', recent_24h_text)
        if match:
            shop_info['24小时下单'] = match.group(1)
        else:
            shop_info['24小时下单'] = ''
    else:
        shop_info['24小时下单'] = ''

    return shop_info


def 单店查询(dizhi, dianming):
    """查询单个店铺并返回提取的信息"""
    输入地址(dizhi)
    输入竞对店名(dianming)

    success = False
    for _ in range(5):
        if check_text_in_region():
            重新搜索()
        else:
            success = True
            break

    shop_info = {}
    if success:
        time.sleep(3)
        shop_info = extract_shop_info()

    返回主页()

    shop_info['店铺名称'] = dianming
    return shop_info


def 写入单条数据(record):
    """将单条数据写入数据库"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # 处理距离字段转换
        distance = record.get('距离', '')
        distance_km = 0.0
        if distance:
            if distance.endswith('km'):
                distance_km = float(distance.replace('km', ''))
            elif distance.endswith('m'):
                distance_km = float(distance.replace('m', '')) / 1000

        # 处理24小时销量 (来自24小时下单)
        daily_sales = record.get('24小时下单', '0')
        try:
            daily_sales = int(daily_sales) if daily_sales else 0
        except:
            daily_sales = 0

        # 处理订单量 (来自销售量)
        total_sales = record.get('销售量', '0')
        # 处理带单位的销售量（如"2.5万"）
        if '万' in total_sales or 'w' in total_sales or 'W' in total_sales:
            num_part = re.search(r'[\d\.]+', total_sales)
            if num_part:
                try:
                    total_sales = float(num_part.group()) * 10000
                except:
                    total_sales = 0
        else:
            try:
                total_sales = float(total_sales) if total_sales else 0
            except:
                total_sales = 0

        # 处理评分
        rating = record.get('评分', '0')
        try:
            rating = float(rating) if rating else 0.0
        except:
            rating = 0.0

        # 处理起送费和配送费
        start_fee = record.get('起送费', '0')
        delivery_fee = record.get('配送费', '0')
        try:
            start_fee = float(start_fee) if start_fee else 0.0
        except:
            start_fee = 0.0
        try:
            delivery_fee = float(delivery_fee) if delivery_fee else 0.0
        except:
            delivery_fee = 0.0

        # 构建插入SQL
        sql = """
        INSERT INTO `竞对每日统计` 
        (`日期`, `竞对id`, `竞对名称`, `订单量`, `24小时销量`, `距离km`, `起送价`, `配送费`, `店铺评分`, `神券活动`, `店铺活动`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            current_date,
            record['竞对id'],
            record['竞对名称'],
            total_sales,  # 订单量来自销售量字段
            daily_sales,  # 24小时销量来自24小时下单字段
            distance_km,
            start_fee,
            delivery_fee,
            rating,
            record.get('神券活动', '无'),
            record.get('店铺活动', '')
        )

        cursor.execute(sql, values)
        connection.commit()
        cursor.close()
        connection.close()
        print(f"成功写入竞对ID {record['竞对id']} 的数据到数据库")
        return True
    except mysql.connector.Error as err:
        print(f"数据库写入错误: {err}")
        return False


def main():
    # 获取需要处理的数据（排除当天已查询的）
    store_data = 从数据库读取数据()

    if not store_data:
        # 检查是否有剩余数据未处理
        last_id = 获取最后处理的竞对id()
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        query = f"SELECT COUNT(*) FROM `竞对门店档案` WHERE `竞对id` > {last_id}"
        cursor.execute(query)
        remaining_count = cursor.fetchone()[0]
        cursor.close()
        connection.close()

        if remaining_count > 0:
            print(f"当天数据已全部查询完成，但仍有 {remaining_count} 条数据待处理")
        else:
            print("所有数据已处理完成")

        # 删除状态文件
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        return

    print(f"本次将处理 {len(store_data)} 条数据")

    # 获取最后处理的竞对ID（用于更新状态）
    last_processed_id = 获取最后处理的竞对id()

    for data in store_data:
        dizhi, dianming, jingdui_id, mendian_id = data
        print(f"处理地址: {dizhi}, 店名: {dianming}, 竞对ID: {jingdui_id}")

        shop_info = 单店查询(dizhi, dianming)
        shop_info['竞对id'] = jingdui_id
        shop_info['竞对名称'] = dianming
        shop_info['门店id'] = mendian_id

        # 写入单条数据
        if 写入单条数据(shop_info):
            print(f"成功处理竞对ID: {jingdui_id}")
            # 更新最后处理的竞对ID
            if jingdui_id > last_processed_id:
                last_processed_id = jingdui_id
                保存最后处理的竞对id(jingdui_id)
        else:
            print(f"处理竞对ID: {jingdui_id} 失败，跳过继续")

    # 检查是否还有剩余数据
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()
    query = f"SELECT COUNT(*) FROM `竞对门店档案` WHERE `竞对id` > {last_processed_id}"
    cursor.execute(query)
    remaining_count = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    if remaining_count > 0:
        print(f"本次处理完成，仍有 {remaining_count} 条数据待处理，请再次运行程序继续")
    else:
        print("所有数据处理完成")
        # 删除状态文件
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)


if __name__ == "__main__":
    main()