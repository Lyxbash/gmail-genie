import { NavLink } from "react-router-dom";
import { useDeveloperMode } from "../hooks/useDeveloperMode";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/activity", label: "Activity" },
  { to: "/review", label: "Review" },
  { to: "/settings", label: "Settings" },
];

const devLinks = [{ to: "/metrics", label: "Insights" }];

export default function Navbar() {
  const { developerMode } = useDeveloperMode();
  const allLinks = developerMode ? [...links.slice(0, 3), ...devLinks, links[3]] : links;

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        Gmail <span>Genie</span>
        <span className="navbar-tagline">Local-first · labels only</span>
      </div>
      <div className="navbar-links">
        {allLinks.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
