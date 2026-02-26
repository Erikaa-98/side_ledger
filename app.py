import streamlit as st
from database import init_db, get_connection
from datetime import datetime
import pandas as pd
import hashlib
import io
import calendar

st.set_page_config(page_title="副业账本 Pro", layout="wide")
init_db()

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

# ================= 登录/注册 =================
if "user_id" not in st.session_state:
    st.title("副业账本 Pro")
    mode = st.radio("选择", ["登录", "注册"])
    email = st.text_input("邮箱")
    password = st.text_input("密码", type="password")

    if mode == "注册":
        if st.button("注册"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO users (email,password,created_at) VALUES (?,?,?)",
                      (email, hash_password(password), datetime.now()))
            conn.commit()
            conn.close()
            st.success("注册成功")
    else:
        if st.button("登录"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=?", (email,))
            row = c.fetchone()
            conn.close()
            if row and row["password"] == hash_password(password):
                st.session_state.user_id = row["id"]
                st.session_state.user_email = row["email"]
                st.rerun()
            else:
                st.error("登录失败")

# ================= 登录后 =================
else:
    user_id = st.session_state.user_id
    conn = get_connection()
    c = conn.cursor()

    st.sidebar.title("副业账本 Pro")
    page = st.sidebar.radio("菜单", ["Dashboard","机构管理","收入管理"])

    # ================= Dashboard =================
    if page == "Dashboard":
        st.title("Dashboard")

        # --- 本月收入
        month_str = datetime.now().strftime("%Y-%m")
        df_income = pd.read_sql_query("""
        SELECT i.amount, i.income_date, i.institution_id, ins.name as institution_name
        FROM incomes i
        LEFT JOIN institutions ins ON i.institution_id=ins.id
        WHERE i.user_id=? AND i.income_date LIKE ?
        """, conn, params=(user_id, f"{month_str}%"))
        total_income = df_income["amount"].sum() if not df_income.empty else 0

        # --- 月目标
        c.execute("SELECT monthly_target FROM users WHERE id=?", (user_id,))
        monthly_target = c.fetchone()["monthly_target"] or 0
        progress = (total_income/monthly_target*100) if monthly_target>0 else 0

        # --- 签约机构数量
        c.execute("SELECT COUNT(*) as cnt FROM institutions WHERE user_id=? AND status='已签约'", (user_id,))
        signed_insts_count = c.fetchone()["cnt"]

        # --- 私活数量
        c.execute("SELECT COUNT(*) as cnt FROM incomes WHERE user_id=? AND (institution_id IS NULL OR institution_id=0) AND income_date LIKE ?", (user_id, f"{month_str}%"))
        private_count = c.fetchone()["cnt"]

        # --- 显示指标卡
        col1,col2,col3,col4,col5 = st.columns(5)
        col1.metric("本月收入", f"¥{total_income}")
        col2.metric("月目标", f"¥{monthly_target}")
        col3.metric("完成率", f"{progress:.1f}%")
        col4.metric("签约机构", f"{signed_insts_count}")
        col5.metric("私活数量", f"{private_count}")

        # --- 日历显示
        st.subheader("📅 本月收入日历")
        today = datetime.now()
        year, month = today.year, today.month
        _, num_days = calendar.monthrange(year, month)

        daily_income = {day:0 for day in range(1,num_days+1)}
        for _, row in df_income.iterrows():
            day = int(row["income_date"][-2:])
            daily_income[day] += row["amount"]

        # 7列布局
        cols = st.columns(7)
        for day in range(1, num_days+1):
            col = cols[(day-1)%7]
            income = daily_income[day]
            if income > 0:
                if col.button(f"{day} ¥{income}", key=f"day{day}"):
                    # 弹出当天收入明细
                    df_day = pd.read_sql_query("""
                    SELECT i.amount, i.income_date, ins.name as institution_name
                    FROM incomes i
                    LEFT JOIN institutions ins ON i.institution_id=ins.id
                    WHERE i.user_id=? AND i.income_date=?
                    """, conn, params=(user_id, f"{year}-{month:02d}-{day:02d}"))
                    st.subheader(f"{year}-{month:02d}-{day:02d} 收入明细")
                    for _, r in df_day.iterrows():
                        source = r['institution_name'] if r['institution_name'] else "私活"
                        st.write(f"{source}: ¥{r['amount']}")
            else:
                col.markdown(
                    f"<div style='background-color:#f8f9fa;padding:10px;border-radius:8px;text-align:center'>{day}</div>",
                    unsafe_allow_html=True
                )

    # ================= 机构管理 =================
    elif page == "机构管理":
        st.title("机构管理")

        with st.form("add_inst"):
            name = st.text_input("名称")
            status = st.selectbox("状态",
                ["已签约","已派单","暂停","长期无单","已解约","储备中"])
            follow = st.date_input("跟进日期")
            note = st.text_area("备注")
            submitted = st.form_submit_button("新增")
            if submitted:
                c.execute("""
                INSERT INTO institutions 
                (name,status,follow_up_date,note,created_at,user_id)
                VALUES (?,?,?,?,?,?)
                """,(name,status,follow.strftime("%Y-%m-%d"),
                     note,datetime.now(),user_id))
                conn.commit()
                st.rerun()

        df = pd.read_sql_query("""
        SELECT * FROM institutions WHERE user_id=?
        """,conn,params=(user_id,))

        for _,row in df.iterrows():
            with st.expander(row["name"]):
                new_status = st.selectbox("修改状态",
                    ["已签约","已派单","暂停","长期无单","已解约","储备中"],
                    index=["已签约","已派单","暂停","长期无单","已解约","储备中"].index(row["status"]),
                    key=f"s{row['id']}")
                if st.button("更新",key=f"u{row['id']}"):
                    c.execute("UPDATE institutions SET status=? WHERE id=?",
                              (new_status,row["id"]))
                    conn.commit()
                    st.rerun()

                if st.button("删除",key=f"d{row['id']}"):
                    c.execute("DELETE FROM institutions WHERE id=?", (row["id"],))
                    conn.commit()
                    st.rerun()

    # ================= 收入管理 =================
    else:
        st.title("收入管理")

        inst_df = pd.read_sql_query("""
        SELECT id,name FROM institutions WHERE user_id=?
        """,conn,params=(user_id,))
        if inst_df.empty:
            st.warning("请先新增机构")
        else:
            inst_dict = dict(zip(inst_df["name"],inst_df["id"]))

            with st.form("add_income"):
                inst = st.selectbox("机构",["私活"] + list(inst_dict.keys()))
                amount = st.number_input("金额")
                tax = st.number_input("税")
                date = st.date_input("日期")
                submit = st.form_submit_button("新增")
                if submit:
                    institution_id = inst_dict.get(inst,0) if inst!="私活" else 0
                    c.execute("""
                    INSERT INTO incomes
                    (institution_id,amount,tax,income_date,created_at,user_id)
                    VALUES (?,?,?,?,?,?)
                    """,(institution_id,amount,tax,
                         date.strftime("%Y-%m-%d"),
                         datetime.now(),user_id))
                    conn.commit()
                    st.rerun()

            df = pd.read_sql_query("""
            SELECT incomes.*, institutions.name 
            FROM incomes 
            LEFT JOIN institutions ON incomes.institution_id=institutions.id
            WHERE incomes.user_id=?
            """,conn,params=(user_id,))

            if not df.empty:
                output = io.BytesIO()
                with pd.ExcelWriter(output) as writer:
                    df.to_excel(writer,index=False)
                st.download_button(
                    "导出Excel",
                    data=output.getvalue(),
                    file_name="income_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    conn.close()
