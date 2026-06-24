import os
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from openai import OpenAI

# ================= 1. 初始化配置 =================
API_KEY = "sk-2f4053a791b84cd19adc9a172446125f"  # 【务必替换为你的真实API Key】
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 初始化本地轻量级 ChromaDB
chroma_client = chromadb.PersistentClient(path="./.chroma_db")

# 自定义一个完全不需要联网的本地向量生成器
class LocalMockEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
             # 生成一个伪向量，彻底绕过下载模型导致的网络超时
             mock_vector = [ord(c) % 10 / 10.0 for c in text[:100]]
             mock_vector += [0.0] * (100 - len(mock_vector))
             embeddings.append(mock_vector)
        return embeddings

custom_ef = LocalMockEmbeddingFunction()

# 创建数据集，强制使用刚才写的免联网生成器
collection = chroma_client.get_or_create_collection(name="business_rules", embedding_function=custom_ef)

# ================= 2. 知识库初始化 =================
def init_knowledge_base():
    print("📦 正在向本地 ChromaDB 录入高阶业务知识库 (PM & DA 终极版)...")
    
    # 🌟 【核心创新】：将单点排查升级为 AARRR 跨层与前瞻性诊断体系
    rules = [
        # 基础规范
        "规范1: 在本产品中，Android买量渠道（paid_ads）的加购到支付转化率如果低于15%，属于二级严重预警。",
        "规范2: 本产品各个指标的标准计算口径：DAU是指当天至少触发过1次 login 事件的去重用户总数。",
        
        # 🚀 发力点一：AARRR 漏斗跨层联动归因
        "规范3 (AARRR 跨层联动防线): 当诊断发现漏斗底层（如『支付转化率』或『Revenue』）发生暴跌时，严禁只在支付环节找原因！必须强制要求排查漏斗顶层的获客质量（Acquisition）。如果底层转化暴跌的同时，顶层新增用户（如 login 或 install 事件）异常飙升，请直接判定为：『疑似渠道端买入了大量低质流量（或羊毛党），导致漏斗底层承接被严重稀释』。",
        
        # 🚀 发力点四：从“滞后总结”到“前瞻预警”
        "规范4 (Leading Indicators 前置预警法则): 在进行业务诊断时，必须区分『滞后指标』和『前置指标』。交易额（Revenue）和支付转化是滞后结果；而『日活用户数(login)』、『浏览商品频次(view_item)』是判断用户生命周期健康度的核心前置指标。即使当前支付数据尚未崩盘，一旦发现 view_item 频次出现下滑趋势，必须在报告中明确发出防患未然的预警：『用户粘性底座开始动摇，预计 3-5 天后将传导至变现端』。"
    ]
    ids = [f"rule_{i}" for i in range(len(rules))]
    
    # 存入数据库
    collection.upsert(documents=rules, ids=ids)
    print("✅ 知识库初始化成功！高阶商业逻辑已注入。")

# ================= 3. RAG 检索逻辑 =================
def retrieve_business_knowledge(user_query, n_results=1):
    results = collection.query(
        query_texts=[user_query],
        n_results=n_results
    )
    if results and results['documents'] and len(results['documents'][0]) > 0:
        return results['documents'][0][0]
    return "未找到相关业务规范。"

# ================= 4. 升级版分析师 =================
def agent_analyst_with_rag(user_query, data_string, intent):
    print("🔍 RAG引擎: 正在检索业务知识库...")
    business_knowledge = retrieve_business_knowledge(user_query)
    print(f"   💡 检索到的相关规范: {business_knowledge}")
    
    system_prompt = f"你是一个资深商业分析师。在撰写报告时，你必须严格遵守以下公司的业务规范：\n{business_knowledge}"
    prompt = f"任务意图:{intent}\n用户问题:{user_query}\n执行结果:\n{data_string}\n请输出专业分析报告。"
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    init_knowledge_base()
    mock_data = "| event_type | count |\n| login | 1500 |\n| add_cart | 600 |\n| purchase | 50 |"
    report = agent_analyst_with_rag("分析一下Android端paid_ads转化率低的问题", mock_data, "[DIAGNOSE]")
    print("\n📊 报告输出：\n", report)