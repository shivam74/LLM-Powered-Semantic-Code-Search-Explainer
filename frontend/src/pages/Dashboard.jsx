import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';

const Dashboard = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await api.get('/files/projects');
      setProjects(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('name', newProjectName);
    if (newProjectDesc) formData.append('description', newProjectDesc);

    try {
      await api.post('/files/projects', formData);
      setIsModalOpen(false);
      setNewProjectName('');
      setNewProjectDesc('');
      fetchProjects();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Your Projects</h2>
          <p className="text-gray-400 text-sm mt-1">Manage your codebases and perform semantic searches.</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md transition-colors text-sm font-medium"
        >
          + New Project
        </button>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-4 flex flex-col pt-10 items-center justify-center">
          <div className="h-8 w-32 bg-gray-800 rounded"></div>
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-20 border-2 border-dashed border-gray-700 rounded-xl bg-gray-800/30">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-white">No projects</h3>
          <p className="mt-1 text-sm text-gray-400">Get started by creating a new project.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <motion.div
              key={project.id}
              whileHover={{ scale: 1.02 }}
              className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden hover:border-gray-500 transition-colors"
            >
              <Link to={`/project/${project.id}`} className="block p-6 h-full flex flex-col justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white">{project.name}</h3>
                  <p className="mt-2 text-sm text-gray-400 line-clamp-2">
                    {project.description || 'No description provided.'}
                  </p>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-700 flex justify-between items-center">
                  <span className="text-xs text-gray-500">
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </span>
                  <span className="text-blue-500 text-sm flex items-center group-hover:translate-x-1 transition-transform">
                    View
                    <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </span>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-gray-800 rounded-xl shadow-2xl max-w-md w-full border border-gray-700 p-6"
          >
            <h3 className="text-lg font-medium text-white mb-4">Create New Project</h3>
            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Auth Microservice"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Description (Optional)</label>
                <textarea
                  value={newProjectDesc}
                  onChange={(e) => setNewProjectDesc(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-24"
                  placeholder="What is this project about?"
                />
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors"
                >
                  Create Project
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
