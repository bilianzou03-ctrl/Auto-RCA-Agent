import streamlit as st
import pandas as pd
# 修复了导入路径，直接引入新版图架构中的路由节点
from agent_graph import router_node

st.set_page_config(page_title="Auto-RCA 工业级诊断中台", page_icon="🕵️‍♂️", layout="wide")
st.title("Auto-RCA 工业级商业数据智能诊断 Agent")

# 初始化 Session 状态机
if "step" not in st.session_state:
    st.session_state.step = "waiting_input"  # 状态流转控制
if "current_state" not in st.session_state:
    st.session_state.current_state = {}

# 重新开始按钮
if st.button("🔄 开启新一轮业务排查"):
    st.session_state.step = "waiting_input"
    st.session_state.current_state = {}
    st.rerun()

# ================= 阶段 1：等待用户发起提问 =================
if st.session_state.step == "waiting_input":
    user_query = st.text_input("请输入您需要洞察的核心业务问题：", 
                               value="老板觉得Android买量渠道转化差，帮我做个漏斗诊断并找出最核心的异常断层。")
    
    if st.button("🚀 启动全链路智能体探查"):
        if user_query:
            with st.spinner("🧠 正在唤醒全链路 Agent 进行架构分发与算法生成..."):
                # 1. 率先跑完前置的意图解析
                routing_result = router_node({"user_query": user_query})
                intent = routing_result["intent"]
                
                # 初始化状态接力棒
                init_state = {
                    "user_query": user_query,
                    "intent": intent,
                    "retry_count": 0,
                    "error_msg": ""
                }
                
                # 调用后台生成一轮时序 SQL
                from agent_graph import sql_generator_node
                updated_state = sql_generator_node(init_state)
                init_state.update(updated_state)
                
                # 保存状态，推进到 HITL 审查阶段
                st.session_state.current_state = init_state
                st.session_state.step = "hitl_review"
                st.rerun()

# ================= 阶段 2：HITL（人工内嵌）黑盒破解与验证面板 =================
# ================= 阶段 2：HITL（人工内嵌）黑盒破解与验证面板 =================
elif st.session_state.step == "hitl_review":
    state = st.session_state.current_state
    
    st.warning("⚠️ **【Human-in-the-Loop 安全红线拦截】大模型 Text-to-SQL 逻辑已生成，请数据资产所有者进行最终合规性审核：**")
    
    # 🌟 【修复点：打破信息差】如果这轮是从执行失败被打回来的，把数据库真实的报错贴在脸上！
    if state.get("error_msg") and "人工审核未通过" not in state.get("error_msg"):
        st.error(f"🛑 底层沙箱拒绝执行！数据库原始报错如下：\n`{state['error_msg']}`\n💡 提示：这通常是因为大模型使用了不支持的 SQL 函数（如 MySQL 方言）。请手动修改下方 SQL 或打回重写。")
    
    # 攻克漏洞一：打破黑盒，将生成的 SQL 变为可直接二次编辑的文本框
    editable_sql = st.text_area("🔧 您可以双击直接修改这段底层查询语句以确保绝对准确（数据安全沙箱控制）：", 
                                value=state.get("sql_query", ""), height=180)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 确认逻辑无误，授权执行安全沙箱取数"):
            state["sql_query"] = editable_sql  # 将人工微调后的 SQL 存回接力棒
            st.session_state.current_state = state
            st.session_state.step = "executing_pipeline"
            st.rerun()
    with col2:
        if st.button("❌ 逻辑有误，打回让大模型重写"):
            # 【修复点】：增加一个明确的加载动画，安抚用户等待焦虑
            with st.spinner("🔄 正在让大模型重新思考并修正 SQL 逻辑，请稍候..."):
                state["error_msg"] = "人工审核未通过：由于统计口径不准，请重新理清指标并写出SQL。"
                from agent_graph import sql_generator_node
                state.update(sql_generator_node(state))
                st.session_state.current_state = state
                st.rerun()

# ================= 阶段 3：全自动化多维交叉执行与渲染阶段 =================
elif st.session_state.step == "executing_pipeline":
    state = st.session_state.current_state
    
    with st.status("⛓️ 正在执行全链路状态图网格流转...", expanded=True) as status:
        # 1. 执行一轮数据库取数
        st.write("🏃 执行节点: `DB_Executor` (一轮大盘同环比抽样)")
        from agent_graph import db_executor_node
        state.update(db_executor_node(state))
        
        if state.get("error_msg"):
            st.error(f"一轮查询失败，图流转自动触发自省: {state['error_msg']}")
            st.session_state.step = "hitl_review"
            status.update(label="链路阻断，返回修正", state="error")
            if st.button("返回修正面板"):
                st.rerun()
            st.stop()
            
        # 2. 核心大招：执行自动交叉立体切片
        st.write("🏃 执行节点: `Hypothesis_Tester` (执行 os X channel 立体交叉假设检验)")
        from agent_graph import hypothesis_tester_node
        state.update(hypothesis_tester_node(state))
        
        # 3. 终极润色：高管报告起草
        st.write("🏃 执行节点: `Analyst` (提炼 Business Sense 高管决策晨报)")
        from agent_graph import analyst_node
        state.update(analyst_node(state))
        
        status.update(label="🎉 工业级全链路诊断编排圆满完成！数据已完全沉淀。", state="complete")

    # ================= 📊 产品层级可视化数据面板展示 =================
    st.markdown("## 📊 诊断结果看板")
    
    tab1, tab2, tab3 = st.tabs(["💡 高管决策诊断报告", "📆 基础时序矩阵数据", "📐 立体交叉检验矩阵 (去流失断层)"])
    
    with tab1:
        st.markdown("### 📝 首席商业分析师报告")
        st.success(state.get("final_report", "报告生成失败"))
        
    with tab2:
        st.markdown("### ⏳ 第一轮：时序基准线汇总报表")
        st.code(state.get("sql_query", ""), language="sql")
        try:
            st.markdown(state.get("data_string", ""))
        except:
            st.write(state.get("data_string", ""))
            
    with tab3:
        st.markdown("### 🔲 第二轮：多维特征交叉假设检验矩阵")
        st.code(state.get("drill_down_sql", ""), language="sql")
        try:
            st.markdown(state.get("drill_down_data", ""))
        except:
            st.write(state.get("drill_down_data", ""))