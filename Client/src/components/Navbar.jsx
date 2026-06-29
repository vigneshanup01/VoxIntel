import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header className="navbar">
      <div className="navbar__links">
        <Link to="/" className="navbar__brand">
          VoxIntel
        </Link>
        {user && (
          <nav className="navbar__nav">
            <Link to="/search">Search</Link>
            <Link to="/analytics">Analytics</Link>
          </nav>
        )}
      </div>
      {user && (
        <div className="navbar__user">
          <span>{user.full_name || user.email}</span>
          <button onClick={logout}>Log out</button>
        </div>
      )}
    </header>
  );
}
