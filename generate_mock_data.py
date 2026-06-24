import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_mock_database():
    # 1. 连接本地 SQLite 数据库（如果不存在会自动创建）
    conn = sqlite3.connect('business_data.db')
    cursor = conn.cursor()

    print("正在初始化数据库表结构...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50),
            event_type VARCHAR(50),  -- login, view_item, add_cart, purchase
            os VARCHAR(20),          -- iOS, Android
            channel VARCHAR(50),     -- organic, paid_ads
            event_time TIMESTAMP,
            revenue DECIMAL(10, 2)
        )
    ''')

    # 2. 生成模拟数据 (模拟过去 14 天的数据)
    print("正在生成模拟业务数据，请稍候...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)
    
    events = []
    current_date = start_date
    
    while current_date <= end_date:
        # 基础流量：每天约 1000 个活跃用户
        daily_users = np.random.randint(800, 1200)
        
        # 【埋点：制造一个异常数据】
        # 假设在第 10 天，Android 端 paid_ads（买量渠道）的支付转化率暴跌（模拟由于发版导致的 bug）
        is_bug_day = (end_date - current_date).days <= 4
        
        for _ in range(daily_users):
            user_id = f"uid_{np.random.randint(10000, 99999)}"
            os = np.random.choice(['iOS', 'Android'], p=[0.4, 0.6])
            channel = np.random.choice(['organic', 'paid_ads'], p=[0.7, 0.3])
            
            # 必定触发 login
            events.append((user_id, 'login', os, channel, current_date + timedelta(minutes=np.random.randint(0, 1440)), 0))
            
            # 漏斗转化逻辑
            if np.random.random() > 0.2: # 80% 会看商品
                events.append((user_id, 'view_item', os, channel, current_date + timedelta(minutes=np.random.randint(1, 1440)), 0))
                
                if np.random.random() > 0.5: # 看商品后 50% 加购
                    events.append((user_id, 'add_cart', os, channel, current_date + timedelta(minutes=np.random.randint(2, 1440)), 0))
                    
                    # 正常情况 30% 购买，Bug 期间 Android 买量渠道仅 2% 购买
                    purchase_rate = 0.3
                    if is_bug_day and os == 'Android' and channel == 'paid_ads':
                        purchase_rate = 0.02 
                        
                    if np.random.random() < purchase_rate: 
                        revenue = round(np.random.uniform(10, 299), 2)
                        events.append((user_id, 'purchase', os, channel, current_date + timedelta(minutes=np.random.randint(3, 1440)), revenue))

        current_date += timedelta(days=1)

    # 3. 批量插入数据库
    cursor.executemany('''
        INSERT INTO user_events (user_id, event_type, os, channel, event_time, revenue)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', events)
    
    conn.commit()
    conn.close()
    print("✅ 成功生成 business_data.db 数据库文件！包含各类转化和异动指标。")

if __name__ == "__main__":
    create_mock_database()