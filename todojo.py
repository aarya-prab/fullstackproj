import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import altair as alt

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TodoJo Pro",
    page_icon="✅",
    layout="wide"
)

# ─── Database Setup ─────────────────────────────────────────────────────────────
conn = sqlite3.connect("todojo_pro.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT,
    due_date TEXT,
    tags TEXT,
    status TEXT,
    created_at TEXT
)
""")
conn.commit()

# ─── Helpers ────────────────────────────────────────────────────────────────────
def fetch_tasks():
    df = pd.read_sql("SELECT * FROM tasks", conn, parse_dates=["due_date","created_at"])
    df["due_date"] = pd.to_datetime(df["due_date"]).dt.date
    return df

def add_task(title, desc, prio, due, tags):
    c.execute("""
      INSERT INTO tasks (title, description, priority, due_date, tags, status, created_at)
      VALUES (?,?,?,?,?,?,?)
    """, (
      title, desc, prio, due.isoformat(), tags, "Pending",
      datetime.now().isoformat()
    ))
    conn.commit()

def update_task(id, **kwargs):
    cols = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [id]
    c.execute(f"UPDATE tasks SET {cols} WHERE id=?", vals)
    conn.commit()

def delete_task(id):
    c.execute("DELETE FROM tasks WHERE id=?", (id,))
    conn.commit()

# ─── Sidebar: Filters & Export ──────────────────────────────────────────────────
st.sidebar.header("🔍 Filters")
status_f = st.sidebar.multiselect(
    "Status", ["Pending","In Progress","Completed"], 
    default=["Pending","In Progress","Completed"]
)
prio_f = st.sidebar.multiselect(
    "Priority", ["Low","Medium","High"], 
    default=["Low","Medium","High"]
)
due_f = st.sidebar.date_input("Due Before", value=None)
tag_f = st.sidebar.text_input("Tag contains")

if st.sidebar.button("Export CSV"):
    df_all = fetch_tasks()
    csv = df_all.to_csv(index=False)
    st.sidebar.download_button("Download CSV", csv, "todojo_tasks.csv")

# ─── Main: Tabs ─────────────────────────────────────────────────────────────────
tabs = st.tabs(["➕ Add Task", "📋 Task List", "📊 Analytics"])
df = fetch_tasks()

with tabs[0]:
    st.header("Add a New Task")
    with st.form("add_form", clear_on_submit=True):
        t1, t2 = st.columns([2,1])
        title    = t1.text_input("Title")
        due_date = t2.date_input("Due date", value=date.today())
        desc     = st.text_area("Description", height=80)
        prio_col, tags_col = st.columns(2)
        priority = prio_col.selectbox("Priority", ["Low","Medium","High"])
        tags_in  = tags_col.text_input("Tags (comma-sep)")
        submitted = st.form_submit_button("Add Task")
        if submitted:
            if not title.strip():
                st.error("Title is required")
            else:
                add_task(title.strip(), desc.strip(), priority, due_date, tags_in.strip())
                st.success("✅ Task added!")

with tabs[1]:
    st.header("Your Tasks")
    # Apply filters
    df = df[df["status"].isin(status_f)]
    df = df[df["priority"].isin(prio_f)]
    if due_f:
        df = df[df["due_date"] <= due_f]
    if tag_f:
        df = df[df["tags"].str.contains(tag_f, case=False, na=False)]

    if df.empty:
        st.info("No tasks match your filters.")
    else:
        for row in df.itertuples():
            cols = st.columns([0.05,2,1,1,1,1])
            # status checkbox
            checked = cols[0].checkbox(
                "", 
                value=(row.status=="Completed"), 
                key=f"cb_{row.id}"
            )
            new_status = (
                "Completed" if checked
                else ("In Progress" if row.status=="In Progress" else "Pending")
            )
            if new_status != row.status:
                update_task(row.id, status=new_status)
                st.success("Status updated!")

            # title + description
            cols[1].markdown(
                f"**{row.title}**  \n{row.description or '_no description_'}"
            )
            cols[2].write(row.priority)
            cols[3].write(row.due_date)
            cols[4].write(row.tags)
            
            # Edit & Delete
            if cols[5].button("✏️ Edit", key=f"edit_{row.id}"):
                st.session_state["edit_id"] = row.id
            if cols[5].button("🗑️ Delete", key=f"del_{row.id}"):
                delete_task(row.id)
                st.success("🗑️ Deleted!")

        # Edit form
        if "edit_id" in st.session_state:
            eid = st.session_state.pop("edit_id")
            task = df[df.id==eid].iloc[0]
            st.markdown("---")
            st.subheader("Edit Task")
            with st.form("edit_form"):
                e_title  = st.text_input("Title", value=task.title)
                e_due    = st.date_input("Due date", value=task.due_date)
                e_desc   = st.text_area("Description", value=task.description)
                e_prio   = st.selectbox(
                    "Priority", ["Low","Medium","High"],
                    index=["Low","Medium","High"].index(task.priority)
                )
                e_tags   = st.text_input("Tags", value=task.tags)
                e_status = st.selectbox(
                    "Status", ["Pending","In Progress","Completed"],
                    index=["Pending","In Progress","Completed"].index(task.status)
                )
                save = st.form_submit_button("Save Changes")
                if save:
                    update_task(
                        eid,
                        title=e_title.strip(),
                        description=e_desc.strip(),
                        priority=e_prio,
                        due_date=e_due.isoformat(),
                        tags=e_tags.strip(),
                        status=e_status
                    )
                    st.success("✅ Updated!")

with tabs[2]:
    st.header("Analytics")
    df_all = fetch_tasks().fillna({"status":"Unknown","priority":"Unknown"})

    # Status breakdown
    st.subheader("By Status")
    status_chart = alt.Chart(df_all).mark_bar().encode(
        x=alt.X("status:N", title="Status"),
        y=alt.Y("count()", title="Number of Tasks"),
        tooltip=[alt.Tooltip("status:N"), alt.Tooltip("count()")]
    )
    st.altair_chart(status_chart, use_container_width=True)

    # Priority breakdown
    st.subheader("By Priority")
    prio_chart = alt.Chart(df_all).mark_arc().encode(
        theta=alt.Theta("count()", title="Count"),
        color=alt.Color("priority:N", title="Priority")
    )
    st.altair_chart(prio_chart, use_container_width=True)

    # Upcoming tasks
    st.subheader("Upcoming Deadlines")
    upcoming = df_all[df_all.due_date <= date.today() + pd.Timedelta(days=7)]
    if upcoming.empty:
        st.write("No tasks due in the next 7 days.")
    else:
        st.table(
            upcoming[["title","due_date","priority","status"]]
            .sort_values("due_date")
        )

# ─── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("© 2025 TodoJo Pro — Professional To-Do Management")
