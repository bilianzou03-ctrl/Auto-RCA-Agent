import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import json
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    query: str
    target: str

# 填入你完整的 Key
DEEPSEEK_KEY = "sk-..." 
SILICONFLOW_KEY = "sk-..."

client = openai.OpenAI(
    api_key=SILICONFLOW_KEY,
    base_url="https://api.siliconflow.cn/v1"
)

@app.post("/api/v1/analyze")
def analyze(req: AnalyzeRequest):
    # 终极 Prompt：让大模型不仅做意图识别，还根据标的和时间跨度，智能模拟出一整套合理的业务数据
    prompt = f"""
    你是一个高精度的商业化数据模拟仓。当前分析的游戏标的是：'{req.target}'，用户的分析需求是：'{req.query}'。
    请分析他的意图，并严格输出一个符合以下 JSON 格式的字典。不要任何 Markdown 标记（不要 ```json），直接返回纯文本。

    要求：
    1. 判断场景：多时间对比场景 scenario 填 'time_compare'；AB实验场景填 'ab_test'。
    2. 如果是 'time_compare'：
       - time_unit: 提取时间单位（如'天'、'周'、'月'）。
       - time_node_1: 提取第一个对比时间节点的名称（如'第1天'、'上线前15天'）。
       - time_node_2: 提取第二个对比时间节点的名称（如'第3天'、'下线前15天'）。
       - val_1: 根据游戏常识，模拟出 '{req.target}' 在 '{req.query}' 中第一个时间节点合理的实收总流水（单位为万，返回一个纯数字，例如 125.40）。
       - val_2: 模拟出第二个时间节点合理的实收总流水（注意业务逻辑：皮肤或礼包上线后期流水通常会发生 15%~50% 不等的衰减，返回纯数字）。
       - data_list_1: 返回一个包含 7 个数字的数组，代表第一个节点内 7 个子时段的日流水走势（其总和要大致等于 val_1）。
       - data_list_2: 返回一个包含 7 个数字的数组，代表第二个节点内 7 个子时段的日流水走势（其总和要大致等于 val_2）。
    
    示例输出：
    {{"scenario": "time_compare", "time_unit": "天", "time_node_1": "第1天", "time_node_2": "第3天", "val_1": 150.2, "val_2": 95.4, "data_list_1": [20,25,30,25,20,15,15.2], "data_list_2": [12,15,18,15,12,11,12.4]}}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        config_text = response.choices[0].message.content.strip()
        if config_text.startswith("```"):
            config_text = config_text.replace("```json", "").replace("```", "").strip()
            
        config_data = json.loads(config_text)
        return {"status": "success", "config": config_data}
        
    except Exception as e:
        # 降级兜底模拟，保障即使没有 Key 或外网超时，演示也绝对不崩
        v1 = round(random.uniform(50, 300), 2)
        v2 = round(v1 * random.uniform(0.5, 0.8), 2)
        return {
            "status": "success",
            "config": {
                "scenario": "time_compare", "time_unit": "天" if "天" in req.query else "周",
                "time_node_1": "第1天" if "天" in req.query else "第一周",
                "time_node_2": "第3天" if "天" in req.query else "第三周",
                "val_1": v1, "val_2": v2,
                "data_list_1": [round(v1/7*random.uniform(0.8,1.2), 1) for _ in range(7)],
                "data_list_2": [round(v2/7*random.uniform(0.8,1.2), 1) for _ in range(7)]
            }
        }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
