import streamlit as st
from database import init_db, get_connection
from datetime import datetime, timedelta
import pandas as pd
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="副业账本", layout="wide")
init_db()

# ---------------- 用户管理 ----------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login():
    st.title("登录")
    email = st.text_input("邮箱")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, password, email FROM users WHERE email=?", (email,))
        row = c.fetchone()
        conn.close()
        if row and row[1] == hash_password(password):
            st.success("登录成功！")
            st.session_state["user_id"] = row[0]
            st.session_state["user_email"] = row[2]
            st.experimental_rerun()
        else:
            st.error("邮箱或密码错误")

def register():
    st.title("注册新账号")
    email = st.text_input("邮箱")
    password = st.text_input("密码", type="password")
    confirm = st.text_input("确认密码", type="password")
    if st.button("注册"):
        if password != confirm:
            st.error("两次密码不一致")
            return
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=?", (email,))
        if c.fetchone():
            st.error("该邮箱已注册")
        else:
            c.execute("INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)",
                      (email, hash_password(password), datetime.now()))
            conn.commit()
            st.success("注册成功，请登录")
        conn.close()

# ---------------- 邮件提醒 ----------------

def send_reminder_email(to_email, reminders):
    if not reminders:
        return
    html = "<h3>副业账本提醒</h3><ul>"
    for name, date in reminders:
        html += f"<li>{name} 下次跟进日期: {date}</li>"
    html += "</ul>"

    msg = MIMEMultipart()
    msg['From'] = 'your_email@example.com'
    msg['To'] = to_email
    msg['Subject'] = '副业账本：待跟进提醒'
    msg.attach(MIMEText(html, 'html'))

    # 替换成你自己的 SMTP 配置
    server = smtplib.SMTP_SSL('smtp.example.com', 465)
    server.login('your_email@example.com', 'email_password')
    server.sendmail(msg['From'], to_email, msg.as_string())
    server.quit()

# ---------------- 页面分发 ----------------

if "user_id" not in st.session_state:
    mode = st.radio("选择操作", ["登录", "注册"])
    if mode == "登录":
        login()
    else:
        register()
else:
    user_id = st.session_state["user_id"]
    user_email = st.session_state.get("user_email")
    st.sidebar.title("副业账本")
    st.sidebar.radio("选择页面", ["Dashboard", "机构管理", "收入管理"], key="page_radio")
    page = st.session_state.page_radio

    # ---------------- 公共函数 ----------------
    def get_institution_status(inst_id):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT MAX(income_date) FROM incomes WHERE institution_id=? AND user_id=?", (inst_id, user_id))
        last_income = c.fetchone()[0]
        conn.close()
        if last_income:
            last_income_date = datetime.strptime(last_income, "%Y-%m-%d")
            if datetime.now() - last_income_date > timedelta(days=90):
                return "长期无单"
            else:
                return "已派单"
        else:
            return "已签约"

    # ---------------- Dashboard ----------------
    def dashboard():
        conn = get_connection()
        c = conn.cursor()
        current_month = datetime.now().strftime("%Y-%m")
        c.execute("SELECT SUM(amount - tax) FROM incomes WHERE income_date LIKE ? AND user_id=?", (f"{current_month}%", user_id))
        month_income = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM institutions WHERE user_id=?", (user_id,))
        active_institutions = c.fetchone()[0]

        st.title("Dashboard")
        st.write("欢迎使用副业账本！")

        # 快速入口
        col1, col2 = st.columns(2)
        if col1.button("管理机构"):
            st.session_state.page_radio = "机构管理"
            st.experimental_rerun()
        if col2.button("管理收入"):
            st.session_state.page_radio = "收入管理"
            st.experimental_rerun()

        col1, col2 = st.columns(2)
        col1.metric("本月收入", f"¥{month_income}")
        col2.metric("活跃机构", f"{active_institutions}")

        # 今日提醒
        st.subheader("今日提醒")
        today = datetime.now().date()
        reminder_days = today + timedelta(days=7)
        c.execute("SELECT name, follow_up_date FROM institutions WHERE follow_up_date BETWEEN ? AND ? AND user_id=? ORDER BY follow_up_date ASC",
                  (today.strftime("%Y-%m-%d"), reminder_days.strftime("%Y-%m-%d"), user_id))
        reminders = c.fetchall()
        if reminders:
            for name, date in reminders:
                st.info(f"{name} 下次跟进日期: {date}")
            # 邮件推送
            send_reminder_email(user_email, reminders)
        else:
            st.write("暂无近期需要跟进的机构。")

        conn.close()

    # ---------------- 机构管理 ----------------
    def manage_institutions():
        st.title("机构管理")
        conn = get_connection()
        c = conn.cursor()

        with st.form("add_institution"):
            name = st.text_input("机构名称")
            contract_date = st.date_input("签约日期")
            follow_up_date = st.date_input("下次跟进日期")
            note = st.text_area("备注")
            submitted = st.form_submit_button("新增机构")
            if submitted:
                c.execute("INSERT INTO institutions (name, contract_date, follow_up_date, note, created_at, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                          (name, contract_date.strftime("%Y-%m-%d"), follow_up_date.strftime("%Y-%m-%d"), note, datetime.now(), user_id))
                conn.commit()
                st.success(f"机构 {name} 新增成功！")

        c.execute("SELECT id, name, contract_date, follow_up_date, note FROM institutions WHERE user_id=? ORDER BY created_at DESC", (user_id,))
        rows = c.fetchall()
        if rows:
            data = []
            for row in rows:
                inst_id, name, contract_date, follow_up_date, note = row
                status = get_institution_status(inst_id)
                if status == "长期无单":
                    status_display = f"❌ {status}"
                elif status == "已派单":
                    status_display = f"🟢 {status}"
                else:
                    status_display = f"🟡 {status}"
                data.append([inst_id, name, contract_date, follow_up_date, note, status_display])
            df = pd.DataFrame(data, columns=["ID","机构名称","签约日期","下次跟进日期","备注","状态"])
            st.dataframe(df)
        conn.close()

    # ---------------- 收入管理 ----------------
    def manage_incomes():
        st.title("收入管理")
        conn = get_connection()
        c = conn.cursor()

        c.execute("SELECT id, name FROM institutions WHERE user_id=?", (user_id,))
        institutions = c.fetchall()
        if not institutions:
            st.warning("请先新增机构！")
            return
        institution_dict = {name: id for id, name in institutions}

        with st.form("add_income"):
            inst_name = st.selectbox("所属机构", list(institution_dict.keys()))
            amount = st.number_input("金额", min_value=0.0, step=1.0)
            tax = st.number_input("扣税金额", min_value=0.0, step=1.0)
            income_type = st.selectbox("收入类型", ["一次性", "周期性"])
            income_date = st.date_input("收入日期")
            submitted = st.form_submit_button("新增收入")
            if submitted:
                c.execute("INSERT INTO incomes (institution_id, amount, tax, income_type, income_date, created_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (institution_dict[inst_name], amount, tax, income_type, income_date.strftime("%Y-%m-%d"), datetime.now(), user_id))
                conn.commit()
                st.success(f"{inst_name} 收入记录新增成功！")
        conn.close()

    # ---------------- 页面分发 ----------------
    if page == "Dashboard":
        dashboard()
    elif page == "机构管理":
        manage_institutions()
    elif page == "收入管理":
        manage_incomes()