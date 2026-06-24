import sqlite3
import pandas as pd
import re  # 【新增】：导入正则表达式模块，用于精准切割大模型的废话
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from openai import OpenAI

# ================= 1. 基础配置 =================
API_KEY = "sk-2f4053a791b84cd19adc9a172446125f"  # 【务必替换为你的新Key】
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 【修复点】：强化数据字典，加上明确的枚举值，彻底封死大模型的幻觉空间
DB_SCHEMA = """
表名: user_events
【严禁捏造不存在的字段和枚举值！】
字段说明:
- event_id: 事件唯一ID
- user_id: 用户唯一ID
- event_type: 行为事件（【只能是以下四个之一】：login, view_item, add_cart, purchase）
- os: 操作系统（【只能是以下两个之一】：Android, iOS）
- channel: 获客渠道（例如: paid_ads, organic 等）
- event_time: 发生时间 (格式: YYYY-MM-DD HH:MM:SS)
- revenue: 支付金额
"""

# ================= 2. 全局状态机 (State) 升级 =================
class AgentState(TypedDict):
    user_query: str          # 用户原始问题
    intent: str              # 意图路由
    sql_query: str           # 第一轮（大盘/同环比）SQL
    sql_approved: bool       # 人工协同审核标记 (Human-in-the-Loop)
    error_msg: str           # 报错捕获
    data_string: str         # 第一轮真实数据
    drill_down_sql: str      # 第二轮：多维交叉下钻假设检验 SQL
    drill_down_data: str     # 第二轮：交叉切片真实数据
    retry_count: int         # 自省重试计数
    final_report: str        # 包含同环比与下钻的终极商业分析报告

# ================= 3. LangGraph 节点处理函数 =================

def router_node(state: AgentState):
    """节点 1：意图识别"""
    print("🟢 [节点] Router: 识别业务意图...")
    prompt = f"判断意图。只能输出[QUERY]或[DIAGNOSE]。\n用户提问：{state['user_query']}"
    res = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0)
    return {"intent": res.choices[0].message.content.strip()}

def sql_generator_node(state: AgentState):
    """节点 2：同环比大盘 SQL 生成器 (自带强力废话过滤机制)"""
    print("🟢 [节点] SQL_Coder: 编写一轮时序同环比代码...")
    
    if state.get("error_msg"):
        prompt = f"你的SQL报错了。原SQL: {state['sql_query']}\n错误: {state['error_msg']}\n表结构:{DB_SCHEMA}\n请重新修正。"
    else:
        prompt = f"""
        你是一个顶级数据分析师。请根据用户问题写出兼容 SQLite 的 SQL 语句。
        表结构：{DB_SCHEMA}
        
        【🔥 核心商业指标设计规范】
        如果意图是 [DIAGNOSE]（诊断异常），你必须写出计算周同比（Week-over-Week）或双时间窗口对比的复杂 SQL。
        
        【🚫 严禁使用的语法（防崩溃警告）】
        本地环境是纯正的 SQLite！绝对不可以使用 MySQL/PostgreSQL 的高级时间函数！如需时间计算，必须使用 SQLite 原生语法，例如：`date(event_time, '-7 days')`。
        
        用户提问：{state['user_query']}
        """
        
    # 【修改点 1】：明确要求大模型把代码放进代码块里，方便我们提取
    prompt += "\n\n【输出规范】：必须且只能把 SQL 语句放在 ```sql 和 ``` 之间。可以有简短的思考过程，但最终必须提供代码块。"
        
    res = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.0)
    raw_response = res.choices[0].message.content.strip()
    
    # ==========================================
    # 🛡️ 【核心修复 2】：使用正则表达式提取 SQL，无视大模型的废话
    # ==========================================
    sql_match = re.search(r"```sql\s*(.*?)\s*```", raw_response, re.DOTALL | re.IGNORECASE)
    
    if sql_match:
        clean_sql = sql_match.group(1).strip() # 成功提取代码块里的内容
    else:
        # 兜底机制：如果它偏不加 ```sql，那就只能粗暴地把原话清理一下返回
        clean_sql = raw_response.replace("```sql", "").replace("```", "").strip()
    
    current_retry = state.get("retry_count", 0)
    if state.get("error_msg"):
        current_retry += 1
        
    return {"sql_query": clean_sql, "retry_count": current_retry}

def db_executor_node(state: AgentState):
    """节点 3：安全沙箱执行"""
    print(f"🟢 [节点] DB_Executor: 执行一轮 SQL...")
    try:
        conn = sqlite3.connect('business_data.db')
        df = pd.read_sql_query(state['sql_query'], conn)
        conn.close()
        return {"data_string": df.to_markdown(index=False), "error_msg": ""}
    except Exception as e:
        return {"error_msg": str(e)}

def hypothesis_tester_node(state: AgentState):
    """节点 4：立体交叉下钻假设检验官 (攻克漏洞三：拒绝维度单一)"""
    # 如果只是简单基础查询，跳过深挖
    if state["intent"] == "[QUERY]":
        return {"drill_down_sql": "无需下钻", "drill_down_data": "无需下钻"}
        
    print("🟢 [节点] Hypothesis_Tester: 正在执行多维交叉切片假设检验...")
    
    # 结合第一轮的大盘异常结果，自动推演需要交叉下钻的 SQL
    # 结合第一轮的大盘异常结果，自动推演需要交叉下钻的 SQL
    prompt = f"""
    你是一个资深商业数据科学家。目前系统第一轮大盘时序指标查出的异常表格如下：
    {state['data_string']}
    
    用户的原始疑问是：{state['user_query']}
    
    【你的任务】
    为了避免单一归因陷阱，请编写一段高级下钻 SQL。
    该 SQL 必须对 `os`（操作系统）和 `channel`（渠道）进行交叉立方分组聚合（GROUP BY os, channel），将流量立体切片，算出的核心漏斗节点人数。
    
    【🔥 极其重要：数据库结构规范】
    必须严格使用以下真实表名和字段，绝不能自己捏造表名（比如绝对不能写 user_event_log）和字段名：
    {DB_SCHEMA}
    
    只输出纯 SQLite 兼容的 SQL 语句，不要任何 Markdown 包裹。
    """
    res = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0)
    drill_sql = res.choices[0].message.content.strip().replace("```sql", "").replace("```", "").strip()
    
    # 执行二级下钻取数
    try:
        conn = sqlite3.connect('business_data.db')
        df_drill = pd.read_sql_query(drill_sql, conn)
        conn.close()
        drill_data = df_drill.to_markdown(index=False)
    except Exception as e:
        drill_data = f"二级下钻执行失败: {str(e)}"
        
    return {"drill_down_sql": drill_sql, "drill_down_data": drill_data}

def analyst_node(state: AgentState):
    """节点 5：高管级深度商业分析师 (PM & DA 终极演进版)"""
    print("🟢 [节点] Analyst: 整合多维时序矩阵，运用 AARRR 与前瞻视角沉淀最终报告...")
    
    prompt = f"""
    你是一个效力于顶尖互联网大厂的【首席商业数据科学家】。
    老板目前遇到了极其棘手的业务问题，请结合以下两轮深度数据，为老板起草一份具备极高商业敏感度（Business Sense）的决策内参。
    
    老板的核心关切：{state['user_query']}
    
    【底层输入 1：时序同环比大盘基准数据】
    {state['data_string']}
    
    【底层输入 2：维度交叉立体下钻假设检验矩阵】
    {state.get('drill_down_data', '无')}
    
    【🏆 首席分析师报告撰写终极法则】
    你撰写的不是一份枯燥的数字流水账，而是一份直击灵魂的业务处方签。你必须严格遵循以下四层结构：
    
    1. 【定性定损】：不要只罗列数字！基于时序同环比的跌幅，定性这次异常是属于“轻微波动”还是“雪崩式断层”。如果跌幅巨大，请用强烈的危机语气。
    
    2. 【AARRR 跨层立体归因 (核心！)】：
       - 利用交叉下钻数据，精准指出流失发生在哪个人群（如 Android + paid_ads）和哪个节点（如 view_item -> add_cart）。
       - 结合公司业务规范（必须严格遵守知识库规则），不要做“单点归因”。如果是支付掉了但前端流量暴增，必须果断指出这是“顶层流量低质稀释底层漏斗”的跨层问题！
    
    3. 【前置预警与长期健康度研判 (核心！)】：
       - 审视全盘数据，即使某些指标目前看似正常（比如总收入没掉），但如果发现前置指标（如核心互动环节 add_cart 的总盘量）出现萎缩，你必须立刻敲响警钟，指出这会在未来几天传导至变现层。
    
    4. 【高管级立体行动处方】：
       - 给出直接的落地策略。如果是流量质量问题，建议“清洗渠道/切断低质买量”；如果是系统性断层，建议“立刻拉起 P0 级产研联合排查群”。
    """
    
    # 🌟 发力点一与四的灵魂：通过引入 agent_rag，让分析师在写报告前先“翻阅”刚才录入的高阶法则！
    from agent_rag import retrieve_business_knowledge
    business_knowledge = retrieve_business_knowledge(state['user_query'])
    
    system_prompt = f"你是一位拥有十年大厂经验的首席数据架构师。在诊断时，你【必须绝对服从】以下公司的顶级业务铁律：\n{business_knowledge}"
    
    res = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5 # 保持 0.5，让它写出来的报告文字富有张力
    )
    return {"final_report": res.choices[0].message.content}

# ================= 4. 条件路由分支器 =================
def check_sql_status(state: AgentState):
    if state.get("error_msg"):
        if state.get("retry_count", 0) >= 2:
            return "force_abort"
        return "retry_sql"
    return "go_drill_down"

# ================= 5. 工作流图结构组装 =================
builder = StateGraph(AgentState)

builder.add_node("Router", router_node)
builder.add_node("SQL_Generator", sql_generator_node)
builder.add_node("DB_Executor", db_executor_node)
builder.add_node("Hypothesis_Tester", hypothesis_tester_node)
builder.add_node("Analyst", analyst_node)

builder.set_entry_point("Router")
builder.add_edge("Router", "SQL_Generator")
builder.add_edge("SQL_Generator", "DB_Executor")

builder.add_conditional_edges(
    "DB_Executor",
    check_sql_status,
    {
        "retry_sql": "SQL_Generator",
        "force_abort": "Analyst",
        "go_drill_down": "Hypothesis_Tester"
    }
)
builder.add_edge("Hypothesis_Tester", "Analyst")
builder.add_edge("Analyst", END)

# 编译导出图 APP
graph_agent = builder.compile()