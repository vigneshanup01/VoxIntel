import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header className="navbar">
      <Link to="/" className="navbar__brand">
        VoxIntel
      </Link>
      {user && (
        <div className="navbar__user">
          <span>{user.full_name || user.email}</span>
          <button onClick={logout}>Log out</button>
        </div>
      )}
    </header>
  );
}
