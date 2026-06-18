import schedule
import time
import requests
# 直接从咱们的核心大脑里引入现成的功能
from agent_core import execute_with_reflection, agent_analyst

def push_to_webhook(text_content):
    """
    负责将生成的报告通过 Webhook 发送到企业通讯软件（以飞书/企微为例）
    未来的独立网站中，这里可以换成向你的网站前端 WebSocket 推送消息的逻辑
    """
    # ⚠️ 替换为你真实申请的机器人 Webhook URL
    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    
    # 构建企业微信/飞书支持的 Markdown 消息体格式
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"📊 **【Auto-RCA 智能早报】**\n\n{text_content}"
        }
    }
    
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 200:
            print("✅ 消息已成功推送到工作群！")
        else:
            print(f"⚠️ 推送可能失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 网络请求异常: {str(e)}")

def daily_inspection_job():
    """定义每天要自动执行的核心任务"""
    print("\n⏰ 触发定时任务：开始执行每日大盘巡检...")
    
    # 1. 设定每天巡检的固定问题（你可以写得很复杂）
    query = "请拉取昨天 Android 端所有渠道的完整转化漏斗，并严格诊断是否存在低于正常阈值的环节。"
    
    # 2. 调用核心 Agent 执行 (带着咱们写好的自省纠错机制)
    df, sql, err = execute_with_reflection(query)
    
    if err:
        error_msg = f"**巡检阻断**：数据库取数失败，请研发人工介入排查。错误日志: {err}"
        push_to_webhook(error_msg)
        return
        
    data_string = df.to_markdown(index=False)
    
    # 3. 唤醒分析师大脑生成报告
    print("🧠 正在生成诊断报告...")
    report = agent_analyst(query, data_string, "[DIAGNOSE]")
    
    # 4. 推送最终结果
    push_to_webhook(report)

# ================= 定时任务配置 =================

# 设定每天早晨 9:00 准时执行这个巡检任务
schedule.every().day.at("09:00").do(daily_inspection_job)

if __name__ == "__main__":
    print("🚀 自动化监控哨兵已启动！")
    print("📝 目前设定：每天 09:00 自动跑数并推送...")
    
    # 【测试技巧】如果你现在就想看效果，可以把下面这行取消注释，它会立刻执行一次！
    daily_inspection_job()
    
    # 真实的服务器后台会挂起这个死循环，一直静默倒计时
    while True:
        schedule.run_pending()
        time.sleep(60) # 每 60 秒检查一次时间