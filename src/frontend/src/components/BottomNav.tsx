import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "Dashboard", icon: "🏠", end: true },
  { to: "/history", label: "History", icon: "📜", end: false },
  { to: "/charts", label: "Charts", icon: "📈", end: false },
  { to: "/settings", label: "Settings", icon: "⚙️", end: false },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          <span className="icon">{item.icon}</span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
