import React, { useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';

const DashboardLayout = () => {
  const { user, logout } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { name: 'Projects', path: '/dashboard' },
  ];

  return (
    <div className="flex h-screen bg-gray-900 text-white overflow-hidden">
      {/* Sidebar */}
      <motion.div 
        initial={{ x: -250 }}
        animate={{ x: 0 }}
        className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col"
      >
        <div className="h-16 flex items-center px-6 border-b border-gray-700">
          <h1 className="text-xl font-bold text-blue-500">Semantic AI</h1>
        </div>
        
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <Link
              key={item.name}
              to={item.path}
              className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                location.pathname === item.path 
                  ? 'bg-blue-600 text-white' 
                  : 'text-gray-300 hover:bg-gray-700 hover:text-white'
              }`}
            >
              {item.name}
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-700">
          <div className="flex items-center justify-between">
            <div className="truncate pr-2">
              <p className="text-sm font-medium text-white truncate">{user?.username}</p>
              <p className="text-xs text-gray-400 truncate">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 bg-gray-700 hover:bg-red-600 rounded-md text-gray-300 hover:text-white transition-colors"
              title="Logout"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      </motion.div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto bg-gray-900 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
