import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from 'react-leaflet';
import { toast, ToastContainer } from 'react-toastify';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'react-toastify/dist/ReactToastify.css';
import './App.css';

// Fix for default markers in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

// Mock user for demo - in real app this would come from authentication
const MOCK_USER = {
  id: "user_123",
  name: "John Citizen",
  email: "john@example.com",
  role: "citizen"
};

const MOCK_ADMIN = {
  id: "admin_123", 
  name: "Admin User",
  email: "admin@city.gov",
  role: "admin"
};

// WebSocket Hook for real-time notifications
const useWebSocket = (userId) => {
  const ws = useRef(null);
  
  useEffect(() => {
    if (!userId) return;
    
    // Connect to WebSocket
    ws.current = new WebSocket(`${WS_URL}/ws/${userId}`);
    
    ws.current.onopen = () => {
      console.log('WebSocket Connected');
      toast.success('🔔 Real-time notifications enabled');
    };
    
    ws.current.onmessage = (event) => {
      const notification = JSON.parse(event.data);
      
      switch (notification.type) {
        case 'report_created':
          toast.success(`✅ ${notification.message}`);
          break;
        case 'status_update':
          toast.info(`📋 ${notification.message}`);
          break;
        case 'high_priority_report':
          toast.warn(`🚨 ${notification.message}`, { autoClose: 8000 });
          break;
        default:
          toast.info(notification.message);
      }
    };
    
    ws.current.onclose = () => {
      console.log('WebSocket Disconnected');
    };
    
    ws.current.onerror = (error) => {
      console.error('WebSocket Error:', error);
    };
    
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [userId]);
  
  return ws.current;
};

// Custom map icons for different priorities and statuses
const createCustomIcon = (priority, status) => {
  const getColor = () => {
    if (status === 'resolved') return '#10b981'; // green
    if (status === 'in_progress') return '#8b5cf6'; // purple
    if (priority >= 4) return '#ef4444'; // red
    if (priority >= 3) return '#f59e0b'; // orange
    return '#3b82f6'; // blue
  };
  
  return L.divIcon({
    className: 'custom-div-icon',
    html: `<div style="background-color: ${getColor()}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });
};

// Map click handler component
const MapClickHandler = ({ onLocationSelect }) => {
  useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      onLocationSelect(lat, lng);
      toast.info(`📍 Location selected: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
    },
  });
  return null;
};

// Utility Components
const LoadingSpinner = () => (
  <div className="flex justify-center items-center py-8">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
  </div>
);

const StatusBadge = ({ status }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'assigned': return 'bg-blue-100 text-blue-800';
      case 'in_progress': return 'bg-purple-100 text-purple-800';
      case 'resolved': return 'bg-green-100 text-green-800';
      case 'closed': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(status)}`}>
      {status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
    </span>
  );
};

const PriorityBadge = ({ priority }) => {
  const getPriorityColor = (priority) => {
    if (priority >= 4) return 'bg-red-100 text-red-800';
    if (priority >= 3) return 'bg-orange-100 text-orange-800';
    if (priority >= 2) return 'bg-yellow-100 text-yellow-800';
    return 'bg-green-100 text-green-800';
  };

  const getPriorityText = (priority) => {
    if (priority >= 4) return 'High';
    if (priority >= 3) return 'Medium';
    if (priority >= 2) return 'Low';
    return 'Very Low';
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(priority)}`}>
      {getPriorityText(priority)}
    </span>
  );
};

// Reports Map Component
const ReportsMap = () => {
  const [mapReports, setMapReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState(null);

  useEffect(() => {
    fetchMapReports();
  }, []);

  const fetchMapReports = async () => {
    try {
      const response = await axios.get(`${API}/reports/map`);
      setMapReports(response.data);
    } catch (error) {
      console.error('Error fetching map reports:', error);
      toast.error('Failed to load map reports');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  // Default center (can be changed to user's location or city center)
  const defaultCenter = [28.6139, 77.2090]; // Delhi coordinates as example

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-medium text-gray-900">Reports Map</h2>
        <p className="text-sm text-gray-600 mt-1">
          Interactive map showing all reported issues ({mapReports.length} reports)
        </p>
      </div>
      
      <div style={{ height: '500px' }}>
        <MapContainer
          center={defaultCenter}
          zoom={12}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          {mapReports.map((report) => (
            <Marker
              key={report.id}
              position={[report.latitude, report.longitude]}
              icon={createCustomIcon(report.priority, report.status)}
              eventHandlers={{
                click: () => setSelectedReport(report),
              }}
            >
              <Popup>
                <div className="p-2 max-w-xs">
                  <h3 className="font-medium text-gray-900 mb-2">{report.title}</h3>
                  <p className="text-sm text-gray-600 mb-2">{report.description}</p>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Status:</span>
                      <StatusBadge status={report.status} />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Priority:</span>
                      <PriorityBadge priority={report.priority} />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Department:</span>
                      <span className="font-medium">{report.department_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Reported by:</span>
                      <span>{report.user_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Date:</span>
                      <span>{new Date(report.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      
      <div className="px-6 py-3 bg-gray-50 border-t">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <div className="flex items-center space-x-4">
            <div className="flex items-center">
              <div className="w-3 h-3 bg-red-500 rounded-full mr-1"></div>
              <span>High Priority</span>
            </div>
            <div className="flex items-center">
              <div className="w-3 h-3 bg-orange-500 rounded-full mr-1"></div>
              <span>Medium Priority</span>
            </div>
            <div className="flex items-center">
              <div className="w-3 h-3 bg-blue-500 rounded-full mr-1"></div>
              <span>Low Priority</span>
            </div>
            <div className="flex items-center">
              <div className="w-3 h-3 bg-green-500 rounded-full mr-1"></div>
              <span>Resolved</span>
            </div>
          </div>
          <button
            onClick={fetchMapReports}
            className="text-blue-600 hover:text-blue-800 font-medium"
          >
            Refresh Map
          </button>
        </div>
      </div>
    </div>
  );
};
const Header = ({ currentUser, onSwitchUser, currentView, setCurrentView }) => (
  <header className="bg-white shadow-sm border-b">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="flex justify-between items-center py-4">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className="bg-blue-600 text-white p-2 rounded-lg">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-2m-2 0H7m5 0v-2a2 2 0 00-2-2H8a2 2 0 00-2 2v2m12-6V9a2 2 0 00-2-2h-2a2 2 0 00-2-2V5a2 2 0 00-2-2H9a2 2 0 00-2 2v2" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-gray-900">Civic Reporter</h1>
          </div>
          
          {currentUser.role === 'citizen' && (
            <nav className="flex space-x-4">
              <button
                onClick={() => setCurrentView('dashboard')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'dashboard' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setCurrentView('report')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'report' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Report Issue
              </button>
              <button
                onClick={() => setCurrentView('map')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'map' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                🗺️ Map View
              </button>
              <button
                onClick={() => setCurrentView('profile')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'profile' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                My Reports
              </button>
            </nav>
          )}
          
          {currentUser.role === 'admin' && (
            <nav className="flex space-x-4">
              <button
                onClick={() => setCurrentView('admin')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'admin' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Admin Dashboard
              </button>
              <button
                onClick={() => setCurrentView('map')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  currentView === 'map' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                🗺️ Map View
              </button>
            </nav>
          )}
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <div className="text-sm font-medium text-gray-900">{currentUser.name}</div>
            <div className="text-xs text-gray-500 capitalize">{currentUser.role}</div>
          </div>
          <button
            onClick={onSwitchUser}
            className="bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded-md text-sm font-medium text-gray-700"
          >
            Switch User
          </button>
        </div>
      </div>
    </div>
  </header>
);

// Dashboard Component
const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Total Reports</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.total_reports || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Pending</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.pending_reports || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">In Progress</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.in_progress_reports || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Resolved</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.resolved_reports || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Resolved Issues */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Recently Resolved Issues</h3>
          {stats?.recent_resolved?.length > 0 ? (
            <div className="space-y-4">
              {stats.recent_resolved.slice(0, 5).map((report) => (
                <div key={report.id} className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-gray-900">{report.title}</h4>
                    <p className="text-sm text-gray-600">{report.location}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {report.issue_type} • Resolved
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <PriorityBadge priority={report.priority} />
                    <StatusBadge status={report.status} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">No resolved issues yet</p>
          )}
        </div>
      </div>
    </div>
  );
};

// Report Form Component
const ReportForm = ({ currentUser }) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    location: '',
    issue_type: ''
  });
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [selectedCoords, setSelectedCoords] = useState(null);
  const [showMap, setShowMap] = useState(false);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleLocationSelect = (lat, lng) => {
    setSelectedCoords({ lat, lng });
    // Reverse geocoding simulation (in real app, use a geocoding service)
    setFormData(prev => ({
      ...prev,
      location: prev.location || `Location: ${lat.toFixed(4)}, ${lng.toFixed(4)}`
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('title', formData.title);
      formDataToSend.append('description', formData.description);
      formDataToSend.append('location', formData.location);
      formDataToSend.append('user_id', currentUser.id);
      
      if (selectedCoords) {
        formDataToSend.append('latitude', selectedCoords.lat.toString());
        formDataToSend.append('longitude', selectedCoords.lng.toString());
      }
      
      if (formData.issue_type) {
        formDataToSend.append('issue_type', formData.issue_type);
      }
      if (selectedImage) {
        formDataToSend.append('image', selectedImage);
      }

      await axios.post(`${API}/reports`, formDataToSend, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setSubmitted(true);
      setFormData({
        title: '',
        description: '',
        location: '',
        issue_type: ''
      });
      setSelectedImage(null);
      setImagePreview(null);
      setSelectedCoords(null);
      toast.success('🎉 Report submitted successfully! AI is analyzing your submission.');
    } catch (error) {
      console.error('Error submitting report:', error);
      toast.error('❌ Error submitting report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-green-900 mb-2">Report Submitted Successfully!</h3>
          <p className="text-green-700 mb-4">
            Your issue has been reported and analyzed by our AI system for automatic routing to the appropriate department. 
            You'll receive real-time notifications about status updates.
          </p>
          <button
            onClick={() => setSubmitted(false)}
            className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-md font-medium"
          >
            Submit Another Report
          </button>
        </div>
      </div>
    );
  }

  const defaultCenter = [28.6139, 77.2090]; // Default coordinates

  return (
    <div className="max-w-4xl mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form Section */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Report a Civic Issue</h2>
            <p className="text-sm text-gray-600 mt-1">
              Help improve your community by reporting issues. AI will automatically categorize and route your report.
            </p>
          </div>
          
          <form onSubmit={handleSubmit} className="px-6 py-4 space-y-6">
            <div>
              <label htmlFor="title" className="block text-sm font-medium text-gray-700">
                Issue Title *
              </label>
              <input
                type="text"
                name="title"
                id="title"
                required
                value={formData.title}
                onChange={handleInputChange}
                className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder="Brief description of the issue"
              />
            </div>
            
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                Detailed Description *
              </label>
              <textarea
                name="description"
                id="description"
                rows={4}
                required
                value={formData.description}
                onChange={handleInputChange}
                className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder="Provide detailed information about the issue"
              />
            </div>
            
            <div>
              <label htmlFor="location" className="block text-sm font-medium text-gray-700">
                Location *
              </label>
              <input
                type="text"
                name="location"
                id="location"
                required
                value={formData.location}
                onChange={handleInputChange}
                className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder="Street address or landmark"
              />
              {selectedCoords && (
                <p className="text-xs text-green-600 mt-1">
                  📍 Coordinates: {selectedCoords.lat.toFixed(4)}, {selectedCoords.lng.toFixed(4)}
                </p>
              )}
              <button
                type="button"
                onClick={() => setShowMap(!showMap)}
                className="mt-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                {showMap ? '🗺️ Hide Map' : '🗺️ Select Location on Map'}
              </button>
            </div>
            
            <div>
              <label htmlFor="image" className="block text-sm font-medium text-gray-700">
                Upload Image (Optional)
              </label>
              <p className="text-xs text-gray-500 mb-2">AI will analyze the image to help categorize the issue</p>
              <input
                type="file"
                name="image"
                id="image"
                accept="image/*"
                onChange={handleImageChange}
                className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
              {imagePreview && (
                <div className="mt-2">
                  <img src={imagePreview} alt="Preview" className="max-w-xs rounded-lg shadow-sm" />
                </div>
              )}
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => {
                  setFormData({
                    title: '',
                    description: '',
                    location: '',
                    issue_type: ''
                  });
                  setSelectedImage(null);
                  setImagePreview(null);
                  setSelectedCoords(null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Clear
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-6 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {submitting ? 'Submitting...' : 'Submit Report'}
              </button>
            </div>
          </form>
        </div>

        {/* Map Section */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Location Selection</h3>
            <p className="text-sm text-gray-600 mt-1">
              {showMap ? 'Click on the map to select precise location' : 'Enable map to select location visually'}
            </p>
          </div>
          
          {showMap ? (
            <div style={{ height: '400px' }}>
              <MapContainer
                center={defaultCenter}
                zoom={13}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <MapClickHandler onLocationSelect={handleLocationSelect} />
                {selectedCoords && (
                  <Marker position={[selectedCoords.lat, selectedCoords.lng]}>
                    <Popup>
                      <div className="text-center">
                        <p className="font-medium">Selected Location</p>
                        <p className="text-sm text-gray-600">
                          {selectedCoords.lat.toFixed(4)}, {selectedCoords.lng.toFixed(4)}
                        </p>
                      </div>
                    </Popup>
                  </Marker>
                )}
              </MapContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center bg-gray-50">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <p className="text-gray-600">Click "Select Location on Map" to enable map</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// User Reports Component
const UserReports = ({ currentUser }) => {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedReportId, setExpandedReportId] = useState(null);
  const [reportDetails, setReportDetails] = useState({});
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    fetchUserReports();
  }, []);

  const fetchUserReports = async () => {
    try {
      const response = await axios.get(`${API}/reports?user_id=${currentUser.id}`);
      setReports(response.data);
    } catch (error) {
      console.error('Error fetching user reports:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadReportDetails = async (reportId) => {
    setLoadingDetails(true);
    try {
      const response = await axios.get(`${API}/reports/${reportId}`);
      setReportDetails((prev) => ({ ...prev, [reportId]: response.data }));
    } catch (error) {
      console.error('Error loading report details:', error);
      toast.error('Failed to load report details');
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleToggleDetails = async (reportId) => {
    if (expandedReportId === reportId) {
      setExpandedReportId(null);
      return;
    }

    setExpandedReportId(reportId);
    await loadReportDetails(reportId);
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">My Reports</h2>
          <p className="text-sm text-gray-600 mt-1">Track the status of your submitted issues</p>
        </div>
        
        <div className="divide-y divide-gray-200">
          {reports.length > 0 ? (
            reports.map((report) => (
              <div key={report.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="text-base font-medium text-gray-900">{report.title}</h3>
                    <p className="text-sm text-gray-600 mt-1">{report.description}</p>
                    <div className="flex items-center space-x-4 mt-2">
                      <span className="text-xs text-gray-500">
                        📍 {report.location}
                      </span>
                      <span className="text-xs text-gray-500">
                        📋 {report.issue_type}
                      </span>
                      <span className="text-xs text-gray-500">
                        📅 {new Date(report.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 ml-4">
                    <PriorityBadge priority={report.priority} />
                    <StatusBadge status={report.status} />
                  </div>
                </div>
                <div className="mt-3">
                  <button
                    onClick={() => handleToggleDetails(report.id)}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {expandedReportId === report.id ? 'Hide Details' : 'View Details'}
                  </button>
                </div>
                {expandedReportId === report.id && (
                  <div className="mt-4 border-t border-gray-200 pt-4">
                    {loadingDetails ? (
                      <p className="text-sm text-gray-500">Loading details...</p>
                    ) : (
                      <>
                        <div>
                          <h4 className="text-sm font-semibold text-gray-800">Attachments</h4>
                          {reportDetails[report.id]?.attachments?.length ? (
                            <div className="mt-2 flex flex-wrap gap-4">
                              {reportDetails[report.id].attachments.map((attachment) => (
                                <div key={attachment.id} className="w-32">
                                  <img
                                    src={attachment.file_url}
                                    alt="Report attachment"
                                    className="h-24 w-full object-cover rounded border border-gray-200"
                                  />
                                  <p className="mt-1 text-xs text-gray-500 truncate">{attachment.content_type}</p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-2 text-sm text-gray-500">No attachments available yet.</p>
                          )}
                        </div>
                        <div className="mt-4">
                          <h4 className="text-sm font-semibold text-gray-800">History</h4>
                          {reportDetails[report.id]?.history?.length ? (
                            <ul className="mt-2 space-y-2">
                              {reportDetails[report.id].history.map((entry) => (
                                <li key={entry.id} className="text-sm text-gray-600">
                                  <div className="font-medium text-gray-800">
                                    {entry.old_status ? `${entry.old_status} → ${entry.new_status}` : entry.new_status}
                                  </div>
                                  {entry.note && <div className="text-gray-600">{entry.note}</div>}
                                  <div className="text-xs text-gray-400">
                                    {entry.created_at ? new Date(entry.created_at).toLocaleString() : ''}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-sm text-gray-500">No history available.</p>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="px-6 py-8 text-center text-gray-500">
              <p>No reports submitted yet</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Admin Dashboard Component
const AdminDashboard = () => {
  const [reports, setReports] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [statusDrafts, setStatusDrafts] = useState({});
  const [isDetailPanelOpen, setIsDetailPanelOpen] = useState(false);
  const [selectedReportDetails, setSelectedReportDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [activeReportId, setActiveReportId] = useState(null);

  useEffect(() => {
    fetchAdminData();
  }, [selectedDepartment, selectedStatus]);

  const fetchAdminData = async () => {
    try {
      const [reportsRes, deptRes, statsRes] = await Promise.all([
        axios.get(`${API}/reports?department_id=${selectedDepartment}&status=${selectedStatus}`),
        axios.get(`${API}/departments`),
        axios.get(`${API}/dashboard/stats`)
      ]);
      
      setReports(reportsRes.data);
      setDepartments(deptRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Error fetching admin data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (reportId, status) => {
    const currentReport = reports.find((r) => r.id === reportId);
    setStatusDrafts((prev) => {
      const existing = prev[reportId] || {};
      const updated = { ...existing, newStatus: status };
      if (!['resolved', 'closed'].includes(status)) {
        if (existing.preview) {
          URL.revokeObjectURL(existing.preview);
        }
        updated.file = null;
        updated.preview = null;
      }

      if (currentReport && status === currentReport.status && !updated.file) {
        const newDrafts = { ...prev };
        delete newDrafts[reportId];
        return newDrafts;
      }

      return { ...prev, [reportId]: updated };
    });
  };

  const handleFileChange = (reportId, file) => {
    const currentReport = reports.find((r) => r.id === reportId);
    setStatusDrafts((prev) => {
      const existing = prev[reportId] || {};
      if (existing.preview) {
        URL.revokeObjectURL(existing.preview);
      }

      if (!file) {
        const updatedDrafts = { ...prev, [reportId]: { ...existing, file: null, preview: null } };
        const draftStatus = existing.newStatus ?? currentReport?.status;
        if (currentReport && draftStatus === currentReport.status) {
          delete updatedDrafts[reportId];
        }
        return updatedDrafts;
      }

      const previewUrl = URL.createObjectURL(file);
      return { ...prev, [reportId]: { ...existing, file, preview: previewUrl } };
    });
  };

  const loadAdminReportDetails = async (reportId) => {
    setDetailsLoading(true);
    try {
      const response = await axios.get(`${API}/reports/${reportId}`);
      setSelectedReportDetails(response.data);
    } catch (error) {
      console.error('Error loading report details:', error);
      toast.error('Failed to load report details');
    } finally {
      setDetailsLoading(false);
    }
  };

  const viewReportDetails = async (reportId) => {
    setActiveReportId(reportId);
    setIsDetailPanelOpen(true);
    await loadAdminReportDetails(reportId);
  };

  const closeReportDetails = () => {
    setIsDetailPanelOpen(false);
    setSelectedReportDetails(null);
    setActiveReportId(null);
  };

  const updateReportStatus = async (reportId) => {
    const draft = statusDrafts[reportId];
    const currentReport = reports.find((r) => r.id === reportId);
    const newStatus = draft?.newStatus ?? currentReport?.status;
    if (!newStatus) return;

    try {
      const formData = new FormData();
      formData.append('new_status', newStatus);
      formData.append('actor_id', MOCK_ADMIN.id);
      formData.append('note', `Status updated to ${newStatus} by admin`);

      if (draft?.file) {
        formData.append('resolution_image', draft.file);
      }

      await axios.patch(`${API}/reports/${reportId}/status`, formData);
      toast.success('Report status updated');

      if (draft?.preview) {
        URL.revokeObjectURL(draft.preview);
      }

      setStatusDrafts((prev) => {
        const updatedDrafts = { ...prev };
        delete updatedDrafts[reportId];
        return updatedDrafts;
      });

      fetchAdminData();
      if (isDetailPanelOpen && activeReportId === reportId) {
        await loadAdminReportDetails(reportId);
      }
    } catch (error) {
      console.error('Error updating report status:', error);
      toast.error('Error updating status');
    }
  };

  const detail = selectedReportDetails;

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">High Priority</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.high_priority?.length || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Pending</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.pending_reports || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">In Progress</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.in_progress_reports || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Resolved</dt>
                  <dd className="text-lg font-medium text-gray-900">{stats?.resolved_reports || 0}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Filter Reports</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="department" className="block text-sm font-medium text-gray-700 mb-2">
              Department
            </label>
            <select
              name="department"
              id="department"
              value={selectedDepartment}
              onChange={(e) => setSelectedDepartment(e.target.value)}
              className="block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            >
              <option value="">All Departments</option>
              {departments.map((dept) => (
                <option key={dept.id} value={dept.id}>{dept.name}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-2">
              Status
            </label>
            <select
              name="status"
              id="status"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="assigned">Assigned</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Reports Table */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">All Reports</h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Issue</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Priority</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Department</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {reports.map((report) => {
                const department = departments.find(d => d.id === report.auto_routed_department_id);
                const draft = statusDrafts[report.id] || {};
                const selectedStatus = draft.newStatus ?? report.status;
                const requiresAttachment = ['resolved', 'closed'].includes(selectedStatus);
                const hasChanges = selectedStatus !== report.status || !!draft.file;

                return (
                  <tr key={report.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{report.title}</div>
                        <div className="text-sm text-gray-500">{report.issue_type}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {report.location}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <PriorityBadge priority={report.priority} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={report.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {department ? department.name : 'Unassigned'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="space-y-2">
                        <select
                          value={selectedStatus}
                          onChange={(e) => handleStatusChange(report.id, e.target.value)}
                          className="text-xs border-gray-300 rounded-md"
                        >
                          <option value="pending">Pending</option>
                          <option value="assigned">Assigned</option>
                          <option value="in_progress">In Progress</option>
                          <option value="resolved">Resolved</option>
                          <option value="closed">Closed</option>
                        </select>

                        {requiresAttachment && (
                          <div className="space-y-2">
                            <input
                              key={`${report.id}-${draft.file ? 'file' : 'nofile'}`}
                              type="file"
                              accept="image/*"
                              onChange={(e) => handleFileChange(report.id, e.target.files && e.target.files[0] ? e.target.files[0] : null)}
                              className="block w-full text-xs text-gray-600"
                            />
                            {draft.preview && (
                              <img
                                src={draft.preview}
                                alt="Resolution proof preview"
                                className="h-16 w-24 object-cover rounded border border-gray-200"
                              />
                            )}
                            {!draft.file && (
                              <p className="text-xs text-gray-500">Attach proof when resolving or closing a report.</p>
                            )}
                          </div>
                        )}

                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => updateReportStatus(report.id)}
                            disabled={!hasChanges}
                            className={`px-3 py-1 rounded text-xs text-white ${hasChanges ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-300 cursor-not-allowed'}`}
                          >
                            Update
                          </button>
                          <button
                            onClick={() => viewReportDetails(report.id)}
                            className="px-3 py-1 rounded text-xs text-blue-600 hover:text-blue-800"
                          >
                            Details
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {reports.length === 0 && (
          <div className="px-6 py-8 text-center text-gray-500">
            <p>No reports found matching the selected criteria</p>
          </div>
        )}
      </div>

      {isDetailPanelOpen && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h4 className="text-lg font-medium text-gray-900">Report Details</h4>
            <button
              onClick={closeReportDetails}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Close
            </button>
          </div>
          <div className="px-6 py-4">
            {detailsLoading ? (
              <p className="text-sm text-gray-500">Loading details...</p>
            ) : detail?.report ? (
              <div className="space-y-4">
                <div>
                  <h5 className="text-sm font-semibold text-gray-800">Summary</h5>
                  <p className="text-sm text-gray-600 mt-1">{detail.report.description}</p>
                  <div className="mt-2 text-xs text-gray-500 space-y-1">
                    <div>📍 {detail.report.location}</div>
                    <div>📋 {detail.report.issue_type}</div>
                    <div>📅 {detail.report.created_at ? new Date(detail.report.created_at).toLocaleString() : ''}</div>
                  </div>
                  <div className="mt-2 flex items-center space-x-2">
                    <PriorityBadge priority={detail.report.priority} />
                    <StatusBadge status={detail.report.status} />
                  </div>
                </div>

                <div>
                  <h5 className="text-sm font-semibold text-gray-800">Attachments</h5>
                  {detail.attachments?.length ? (
                    <div className="mt-2 flex flex-wrap gap-4">
                      {detail.attachments.map((attachment) => (
                        <div key={attachment.id} className="w-32">
                          <img
                            src={attachment.file_url}
                            alt="Report attachment"
                            className="h-24 w-full object-cover rounded border border-gray-200"
                          />
                          <p className="mt-1 text-xs text-gray-500 truncate">{attachment.content_type}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-gray-500">No attachments uploaded.</p>
                  )}
                </div>

                <div>
                  <h5 className="text-sm font-semibold text-gray-800">History</h5>
                  {detail.history?.length ? (
                    <ul className="mt-2 space-y-2">
                      {detail.history.map((entry) => (
                        <li key={entry.id} className="text-sm text-gray-600">
                          <div className="font-medium text-gray-800">
                            {entry.old_status ? `${entry.old_status} → ${entry.new_status}` : entry.new_status}
                          </div>
                          {entry.note && <div className="text-gray-600">{entry.note}</div>}
                          <div className="text-xs text-gray-400">
                            {entry.created_at ? new Date(entry.created_at).toLocaleString() : ''}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-gray-500">No history recorded.</p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Select a report to view details.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// User Switcher Component
const UserSwitcher = ({ onSelectUser }) => (
  <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div className="sm:mx-auto sm:w-full sm:max-w-md">
      <div className="bg-blue-600 text-white p-3 rounded-lg w-fit mx-auto mb-6">
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-2m-2 0H7m5 0v-2a2 2 0 00-2-2H8a2 2 0 00-2 2v2m12-6V9a2 2 0 00-2-2h-2a2 2 0 00-2-2V5a2 2 0 00-2-2H9a2 2 0 00-2 2v2" />
        </svg>
      </div>
      <h2 className="text-center text-3xl font-extrabold text-gray-900">
        Civic Reporter
      </h2>
      <p className="mt-2 text-center text-sm text-gray-600">
        Choose your role to continue
      </p>
    </div>

    <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
      <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10 space-y-4">
        <button
          onClick={() => onSelectUser(MOCK_USER)}
          className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <div className="flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Continue as Citizen
          </div>
        </button>
        
        <button
          onClick={() => onSelectUser(MOCK_ADMIN)}
          className="group relative w-full flex justify-center py-3 px-4 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <div className="flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-2m-2 0H7m5 0v-2a2 2 0 00-2-2H8a2 2 0 00-2 2v2m12-6V9a2 2 0 00-2-2h-2a2 2 0 00-2-2V5a2 2 0 00-2-2H9a2 2 0 00-2 2v2" />
            </svg>
            Continue as Admin
          </div>
        </button>
        
        <div className="mt-6">
          <div className="text-center text-xs text-gray-500">
            Demo Mode - No real authentication required
          </div>
        </div>
      </div>
    </div>
  </div>
);

// Main App Component
function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [currentView, setCurrentView] = useState('dashboard');
  
  // Initialize WebSocket connection
  const websocket = useWebSocket(currentUser?.id);

  const handleUserSelect = (user) => {
    setCurrentUser(user);
    if (user.role === 'admin') {
      setCurrentView('admin');
    } else {
      setCurrentView('dashboard');
    }
  };

  const handleSwitchUser = () => {
    setCurrentUser(null);
    setCurrentView('dashboard');
  };

  if (!currentUser) {
    return <UserSwitcher onSelectUser={handleUserSelect} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header 
        currentUser={currentUser} 
        onSwitchUser={handleSwitchUser}
        currentView={currentView}
        setCurrentView={setCurrentView}
      />
      
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {currentUser.role === 'citizen' && currentView === 'dashboard' && <Dashboard />}
          {currentUser.role === 'citizen' && currentView === 'report' && <ReportForm currentUser={currentUser} />}
          {currentUser.role === 'citizen' && currentView === 'profile' && <UserReports currentUser={currentUser} />}
          {(currentView === 'map') && <ReportsMap />}
          {currentUser.role === 'admin' && currentView === 'admin' && <AdminDashboard />}
        </div>
      </main>
      
      {/* Toast Notifications Container */}
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="light"
        style={{ zIndex: 9999 }}
      />
    </div>
  );
}

export default App;