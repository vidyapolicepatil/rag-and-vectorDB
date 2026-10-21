import { useEffect, useState } from "react";
import {
  BookOpenText,
  ChartNoAxesCombined,
  FlaskConical,
  House,
  MessageSquareText,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { checkHealth } from "../services/api.js";

const links = [
  { to: "/", label: "Dashboard", icon: House },
  { to: "/chat", label: "Ask Documents", icon: MessageSquareText },
  { to: "/experiments", label: "Experiments", icon: FlaskConical },
  { to: "/research", label: "Research Notes", icon: BookOpenText },
];

export default function Sidebar() {
  const [backendStatus, setBackendStatus] = useState("checking");

  useEffect(() => {
    let active = true;
    const updateStatus = async () => {
      try {
        await checkHealth();
        if (active) setBackendStatus("connected");
      } catch {
        if (active) setBackendStatus("unavailable");
      }
    };
    updateStatus();
    const interval = window.setInterval(updateStatus, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <aside className="sidebar">
      <NavLink to="/" className="brand">
        <span className="brand-mark"><ChartNoAxesCombined size={21} /></span>
        <span className="brand-copy"><strong>Research Lens</strong><small>DOCUMENT INTELLIGENCE</small></span>
      </NavLink>
      <div className="sidebar-label">WORKSPACE</div>
      <nav className="side-nav" aria-label="Main navigation">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            <Icon size={18} strokeWidth={1.9} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className={`sidebar-footer backend-${backendStatus}`} role="status" aria-live="polite">
        <span className="footer-status-dot" />
        {backendStatus === "checking" ? "Checking connection..." : backendStatus === "connected" ? "Backend connected" : "Backend unavailable"}
      </div>
    </aside>
  );
}
