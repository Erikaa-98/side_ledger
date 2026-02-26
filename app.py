import streamlit as st
from database import init_db, get_connection
from datetime import datetime
import pandas as pd
import hashlib
import io

st.set_page_config(page_title="副业账本 Pro", layout="wide")
init_db()

# ================= 登录 =================
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

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

else:

    user_id = st.session_state.user_id
    conn = get_connection()
    c = conn.cursor()

    st.sidebar.title("副业账本 Pro")
    page = st.sidebar.radio("菜单", ["Dashboard","机构管理","收入管理"])

    # ================= Dashboard =================
    if page == "Dashboard":
        st.title("Dashboard")

        # 月收入
        month = datetime.now().strftime("%Y-%m")
        df = pd.read_sql_query("""
        SELECT * FROM incomes WHERE user_id=? AND income_date LIKE ?
        """, conn, params=(user_id, f"{month}%"))

        total = df["amount"].sum() if not df.empty else 0

        # 目标系统
        c.execute("SELECT monthly_target FROM users WHERE id=?", (user_id,))
        target = c.fetchone()["monthly_target"] or 0

        new_target = st.number_input("设置月目标", value=float(target))
        if st.button("保存目标"):
            c.execute("UPDATE users SET monthly_target=? WHERE id=?", (new_target,user_id))
            conn.commit()
            st.success("已保存")
            st.rerun()

        progress = (total/target*100) if target>0 else 0

        col1,col2,col3 = st.columns(3)
        col1.metric("本月收入", f"¥{total}")
        col2.metric("月目标", f"¥{target}")
        col3.metric("完成率", f"{progress:.1f}%")

        if target>0:
            st.progress(min(progress/100,1.0))

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

        # 生命周期评分
        st.subheader("机构评分")
        score_df = pd.read_sql_query("""
        SELECT institutions.name, SUM(incomes.amount) as total
        FROM institutions
        LEFT JOIN incomes ON institutions.id=incomes.institution_id
        WHERE institutions.user_id=?
        GROUP BY institutions.id
        """,conn,params=(user_id,))
        if not score_df.empty:
            st.bar_chart(score_df.set_index("name"))

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
                inst = st.selectbox("机构",list(inst_dict.keys()))
                amount = st.number_input("金额")
                tax = st.number_input("税")
                date = st.date_input("日期")
                submit = st.form_submit_button("新增")
                if submit:
                    c.execute("""
                    INSERT INTO incomes
                    (institution_id,amount,tax,income_date,created_at,user_id)
                    VALUES (?,?,?,?,?,?)
                    """,(inst_dict[inst],amount,tax,
                         date.strftime("%Y-%m-%d"),
                         datetime.now(),user_id))
                    conn.commit()
                    st.rerun()

            df = pd.read_sql_query("""
            SELECT incomes.*, institutions.name 
            FROM incomes 
            JOIN institutions ON incomes.institution_id=institutions.id
            WHERE incomes.user_id=?
            """,conn,params=(user_id,))

            if not df.empty:

                # 导出 Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df.to_excel(writer,index=False)
                st.download_button(
                    "导出Excel",
                    data=output.getvalue(),
                    file_name="income_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # 图表
                df["month"]=df["income_date"].str.slice(0,7)
                monthly=df.groupby("month")["amount"].sum().reset_index()
                st.line_chart(monthly.set_index("month"))

    conn.close()
