import sqlite3
import pandas as pd
from openai import OpenAI

# ================= 1. 基础配置 =================
API_KEY = "sk-2f4053a791b84cd19adc9a172446125f" # 【务必替换为你的新Key】
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

DB_SCHEMA = """
表名: user_events
字段: 
- event_id (整数, 主键)
- user_id (字符串, 用户ID)
- event_type (字符串, 事件类型，仅包含: login, view_item, add_cart, purchase)
- os (字符串, 操作系统，仅包含: iOS, Android)
- channel (字符串, 流量渠道，仅包含: organic, paid_ads)
- event_time (时间戳)
- revenue (浮点数, 支付金额，仅在 purchase 事件中有值，其他为 0)
"""

# ================= 2. 大脑模块 =================

def agent_router(user_query):
    """【角色1：调度员】"""
    prompt = f"判断意图。只能输出[QUERY]或[DIAGNOSE]。\n[QUERY]:查基础数据。\n[DIAGNOSE]:排查异常。\n用户提问：{user_query}"
    response = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0)
    return response.choices[0].message.content.strip()

def agent_text2sql(user_query, error_msg=None, wrong_sql=None):
    """【角色2：取数表哥】(加入了自省机制)"""
    if error_msg:
        # 如果传入了错误信息，进入纠错模式
        prompt = f"""
        你写的SQL报错了。请修正。
        原SQL: {wrong_sql}
        错误信息: {error_msg}
        数据库结构: {DB_SCHEMA}
        只输出修正后的SQL语句本身，不要任何Markdown格式。
        """
    else:
        # 正常生成模式
        prompt = f"""
        写出兼容 SQLite 的 SQL。数据库结构：{DB_SCHEMA}
        规则：1. 只输出 SQL 本身。2. 漏斗转化用 COUNT(DISTINCT user_id)。
        用户提问：{user_query}
        """
    response = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0)
    return response.choices[0].message.content.strip()

def agent_analyst(user_query, data_string, intent):
    """【角色3：首席分析师】(新增启发式引导能力)"""
    
    system_prompt = """
    你是一个互联网大厂的资深商业分析师（拥有极强的 Business Sense）。
    
    【你的核心任务】
    如果意图是诊断，请给出归因结论和下一步排查建议。排版要专业、条理清晰。
    
    【⭐️ 强制规则：启发式引导 (Proactive Prompting) ⭐️】
    在你输出完所有的分析报告后，必须在回答的最末尾，根据当前的上下文，生成一个具体的、有引导性的“下一步交互提示”。
    
    举例说明：
    - 如果你刚刚完成了一次漏斗分析，你可以提示：“**💡 推荐下一步探索：** 是否需要我为您提供使用 Python (Plotly/Echarts) 绘制漏斗图的完整代码及格式要求？”
    - 如果你发现了某个渠道暴跌，你可以提示：“**💡 推荐下一步探索：** 是否需要我进一步为您下钻分析该渠道新老用户的具体留存差异？”
    - 如果你给出了一套行动建议，你可以提示：“**💡 推荐下一步探索：** 是否需要我根据上述结论，帮您直接起草一份给老板的正式汇报邮件？”
    
    务必保证这个提示紧贴当前业务场景，并且必须以 “**💡 推荐下一步探索：**” 开头。
    """
    
    prompt = f"任务意图:{intent}\n用户问题:{user_query}\n执行结果:\n{data_string}\n请输出专业分析报告。"
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query} # 注意这里我微调了一下，让大模型更好地理解上下文
        ],
        temperature=0.6 # 稍微提高一点温度，让它的“追问”更具创造力和发散性
    )
    return response.choices[0].message.content

# ================= 3. 核心执行引擎 (带有自省循环) =================

def execute_with_reflection(user_query, max_retries=2):
    """执行 SQL，如果报错则让大模型重写 (Self-Reflection Loop)"""
    sql_query = agent_text2sql(user_query)
    
    for attempt in range(max_retries + 1):
        try:
            conn = sqlite3.connect('business_data.db')
            df = pd.read_sql_query(sql_query, conn)
            conn.close()
            return df, sql_query, None # 成功返回
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ SQL执行失败 (尝试 {attempt+1}): {error_msg}")
            if attempt < max_retries:
                print("🔄 触发自省机制，正在让大模型修正 SQL...")
                sql_query = agent_text2sql(user_query, error_msg=error_msg, wrong_sql=sql_query)
            else:
                return None, sql_query, error_msg # 彻底失败返回

# 如果单独运行此文件进行测试
if __name__ == "__main__":
    df, sql, err = execute_with_reflection("老板问为什么最近买量渠道转化率掉这么厉害")
    if err:
         print("失败:", err)
    else:
         print("成功取数:\n", df)