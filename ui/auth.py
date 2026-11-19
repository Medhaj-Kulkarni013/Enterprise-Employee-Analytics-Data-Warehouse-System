"""OOP Authentication and Router-Level Role-Based Access Control (RBAC)."""

import hashlib
import hmac
import streamlit as st


class AuthService:
    """Encapsulates authentication and 3-tier RBAC permissions."""

    ROLE_PERMISSIONS = {
        "Data Architect": {
            "Home",
            "Employees",
            "Projects",
            "Performance reviews",
            "Analytics dashboard",
            "Warehouse sync",
        },
        "HR Operations": {
            "Home",
            "Employees",
            "Projects",
            "Performance reviews",
            "Analytics dashboard",
        },
        "Executive": {
            "Home",
            "Analytics dashboard",
        },
    }

    USERS = {
        "architect": {
            "name": "Aryan Pophali (Data Architect)",
            "role": "Data Architect",
            "password_hash": hashlib.sha256(b"arch123").hexdigest(),
        },
        "hr": {
            "name": "Priya Nair (HR Operations)",
            "role": "HR Operations",
            "password_hash": hashlib.sha256(b"hr123").hexdigest(),
        },
        "exec": {
            "name": "Ananya Rao (Executive)",
            "role": "Executive",
            "password_hash": hashlib.sha256(b"exec123").hexdigest(),
        },
    }

    @classmethod
    def current_user(cls):
        """Return the currently authenticated user dict or None."""
        return st.session_state.get("auth_user")

    @classmethod
    def authenticate(cls, username: str, password: str):
        """Verify credentials using constant-time SHA-256 comparison."""
        record = cls.USERS.get(username.strip().lower())
        if not record:
            return None
        candidate_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if hmac.compare_digest(candidate_hash, record["password_hash"]):
            return {
                "username": username.strip().lower(),
                "name": record["name"],
                "role": record["role"],
            }
        return None

    @classmethod
    def is_authorized(cls, role: str, page_title: str) -> bool:
        """Check whether a role is allowed to access a page title."""
        allowed = {p.lower() for p in cls.ROLE_PERMISSIONS.get(role, set())}
        return page_title.strip().lower() in allowed

    @classmethod
    def render_login_page(cls):
        """Render the standalone login screen when no session is active."""
        st.title("🔐 Enterprise Employee Analytics — Sign In")
        st.caption("Role-Based Access Control (RBAC) Portal")
        _, col_center, _ = st.columns([1, 1.3, 1])
        with col_center:
            with st.form("rbac_login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Sign In", type="primary", use_container_width=True
                )
            if submitted:
                authenticated = cls.authenticate(username, password)
                if authenticated:
                    st.session_state["auth_user"] = authenticated
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            with st.expander("Demo Role Credentials"):
                st.markdown(
                    "- **Data Architect (Full Warehouse & ETL):** `architect` / `arch123`\n"
                    "- **HR Operations (OLTP Entry & Analytics):** `hr` / `hr123`\n"
                    "- **Executive (Read-Only OLAP Dashboards):** `exec` / `exec123`"
                )

    @classmethod
    def render_sidebar_session(cls):
        """Display active user badge, role permissions, and logout button."""
        user = cls.current_user()
        if not user:
            return
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"**Signed in as:** {user['name']}")
            st.caption(f"Role: `{user['role']}`")
            allowed = sorted(cls.ROLE_PERMISSIONS.get(user["role"], []))
            st.caption("Access: " + ", ".join(allowed))
            if st.button("Logout", key="rbac_logout_btn", use_container_width=True):
                st.session_state.pop("auth_user", None)
                st.rerun()

    @classmethod
    def enforce(cls, page_title: str, render_sidebar: bool = True):
        """Secondary page-level guard ensuring unauthenticated/unauthorized calls halt."""
        user = cls.current_user()
        if not user:
            cls.render_login_page()
            st.stop()

        if render_sidebar:
            cls.render_sidebar_session()

        if not cls.is_authorized(user["role"], page_title):
            allowed = ", ".join(sorted(cls.ROLE_PERMISSIONS.get(user["role"], [])))
            st.error(
                f"Access Denied: Role **{user['role']}** is not authorized to access **{page_title}**."
            )
            st.info(f"Permitted modules for your role: **{allowed}**")
            st.stop()