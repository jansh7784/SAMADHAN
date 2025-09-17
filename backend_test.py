#!/usr/bin/env python3
"""
Comprehensive Backend Testing for Civic Issue Reporting System
Tests all API endpoints including AI-powered image analysis
"""

import requests
import json
import base64
import io
from PIL import Image
import os
import sys
from datetime import datetime

# Get backend URL from environment
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except:
        pass
    return "https://urbrights.preview.emergentagent.com"

BASE_URL = get_backend_url()
API_URL = f"{BASE_URL}/api"

print(f"Testing backend at: {API_URL}")

class CivicReportingTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.created_user_id = None
        self.created_report_id = None
        
    def log_test(self, test_name, success, message, details=None):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name} - {message}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
    def create_test_image(self):
        """Create a test image for upload testing"""
        # Create a simple test image
        img = Image.new('RGB', (200, 200), color='red')
        
        # Add some visual elements to make it look like a civic issue
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 150, 150], fill='gray', outline='black', width=3)
        draw.text((60, 170), "POTHOLE", fill='white')
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def test_api_health(self):
        """Test basic API health check"""
        try:
            response = self.session.get(f"{API_URL}/")
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("API Health Check", True, f"API is responding: {data['message']}")
                    return True
                else:
                    self.log_test("API Health Check", False, "API response missing message field")
                    return False
            else:
                self.log_test("API Health Check", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("API Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def test_department_initialization(self):
        """Test department initialization"""
        try:
            # First, try to initialize departments
            response = self.session.post(f"{API_URL}/departments/initialize")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Department Initialization", True, data.get("message", "Departments initialized"))
            else:
                self.log_test("Department Initialization", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
            # Then verify departments exist
            response = self.session.get(f"{API_URL}/departments")
            if response.status_code == 200:
                departments = response.json()
                if len(departments) >= 10:  # Should have at least 10 departments
                    dept_names = [d['name'] for d in departments]
                    expected_depts = ["Public Works Department", "Sanitation Department", "Utilities Department"]
                    found_expected = [name for name in expected_depts if name in dept_names]
                    
                    if len(found_expected) >= 2:
                        self.log_test("Department Retrieval", True, f"Found {len(departments)} departments including key ones")
                        return True
                    else:
                        self.log_test("Department Retrieval", False, f"Missing expected departments. Found: {dept_names[:5]}")
                        return False
                else:
                    self.log_test("Department Retrieval", False, f"Only {len(departments)} departments found, expected more")
                    return False
            else:
                self.log_test("Department Retrieval", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Department System", False, f"Error: {str(e)}")
            return False
    
    def test_user_management(self):
        """Test user creation and retrieval"""
        try:
            # Create a realistic test user
            user_data = {
                "name": "Sarah Johnson",
                "email": "sarah.johnson@email.com",
                "phone": "+1-555-0123",
                "role": "citizen"
            }
            
            response = self.session.post(f"{API_URL}/users", json=user_data)
            if response.status_code == 200:
                user = response.json()
                self.created_user_id = user.get("id")
                if self.created_user_id and user.get("name") == user_data["name"]:
                    self.log_test("User Creation", True, f"Created user: {user['name']} (ID: {self.created_user_id})")
                else:
                    self.log_test("User Creation", False, "User created but missing expected fields")
                    return False
            else:
                self.log_test("User Creation", False, f"HTTP {response.status_code}: {response.text}")
                return False
            
            # Test user retrieval
            response = self.session.get(f"{API_URL}/users")
            if response.status_code == 200:
                users = response.json()
                if len(users) > 0:
                    user_found = any(u.get("id") == self.created_user_id for u in users)
                    if user_found:
                        self.log_test("User Retrieval", True, f"Retrieved {len(users)} users including created user")
                        return True
                    else:
                        self.log_test("User Retrieval", False, "Created user not found in user list")
                        return False
                else:
                    self.log_test("User Retrieval", False, "No users returned")
                    return False
            else:
                self.log_test("User Retrieval", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("User Management", False, f"Error: {str(e)}")
            return False
    
    def test_report_creation_with_ai(self):
        """Test report creation with image upload and AI analysis - CRITICAL TEST"""
        if not self.created_user_id:
            self.log_test("Report Creation", False, "No user ID available for testing")
            return False
            
        try:
            # Create test image
            image_data = self.create_test_image()
            
            # Prepare form data for multipart upload
            files = {
                'image': ('pothole.jpg', image_data, 'image/jpeg')
            }
            
            data = {
                'title': 'Large Pothole on Main Street',
                'description': 'There is a dangerous pothole on Main Street near the intersection with Oak Avenue. It\'s about 2 feet wide and 6 inches deep, causing damage to vehicles and creating a safety hazard for drivers.',
                'location': 'Main Street & Oak Avenue, Downtown',
                'user_id': self.created_user_id,
                'issue_type': 'road_damage'
            }
            
            print("Submitting report with image for AI analysis...")
            response = self.session.post(f"{API_URL}/reports", data=data, files=files)
            
            if response.status_code == 200:
                result = response.json()
                report = result.get("report", {})
                ai_analysis = result.get("ai_analysis", {})
                
                self.created_report_id = report.get("id")
                
                # Verify report creation
                if self.created_report_id and report.get("title") == data["title"]:
                    self.log_test("Report Creation", True, f"Report created successfully (ID: {self.created_report_id})")
                else:
                    self.log_test("Report Creation", False, "Report created but missing expected fields")
                    return False
                
                # Verify AI analysis
                if ai_analysis:
                    department = ai_analysis.get("department")
                    priority = ai_analysis.get("priority")
                    issue_type = ai_analysis.get("issue_type")
                    severity_score = ai_analysis.get("severity_score")
                    reasoning = ai_analysis.get("reasoning")
                    
                    if department and priority and issue_type is not None and severity_score is not None:
                        self.log_test("AI Analysis", True, 
                                    f"AI classified as: {department}, Priority: {priority}, Type: {issue_type}, Severity: {severity_score}")
                        
                        # Verify AI reasoning
                        if reasoning:
                            self.log_test("AI Reasoning", True, f"AI provided reasoning: {reasoning[:100]}...")
                        else:
                            self.log_test("AI Reasoning", False, "AI analysis missing reasoning")
                            
                        # Check if department was properly routed
                        if report.get("auto_routed_department_id"):
                            self.log_test("Department Routing", True, "Report automatically routed to department")
                        else:
                            self.log_test("Department Routing", False, "Report not routed to department")
                            
                        return True
                    else:
                        self.log_test("AI Analysis", False, f"AI analysis incomplete: {ai_analysis}")
                        return False
                else:
                    self.log_test("AI Analysis", False, "No AI analysis in response")
                    return False
            else:
                self.log_test("Report Creation with AI", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Report Creation with AI", False, f"Error: {str(e)}")
            return False
    
    def test_report_retrieval_and_filtering(self):
        """Test report retrieval with filtering"""
        try:
            # Test basic report retrieval
            response = self.session.get(f"{API_URL}/reports")
            if response.status_code == 200:
                reports = response.json()
                if len(reports) > 0:
                    self.log_test("Report Retrieval", True, f"Retrieved {len(reports)} reports")
                    
                    # Test filtering by user
                    if self.created_user_id:
                        response = self.session.get(f"{API_URL}/reports?user_id={self.created_user_id}")
                        if response.status_code == 200:
                            user_reports = response.json()
                            if len(user_reports) > 0:
                                self.log_test("Report Filtering by User", True, f"Found {len(user_reports)} reports for user")
                            else:
                                self.log_test("Report Filtering by User", False, "No reports found for created user")
                        else:
                            self.log_test("Report Filtering by User", False, f"HTTP {response.status_code}")
                    
                    # Test filtering by status
                    response = self.session.get(f"{API_URL}/reports?status=pending")
                    if response.status_code == 200:
                        pending_reports = response.json()
                        self.log_test("Report Filtering by Status", True, f"Found {len(pending_reports)} pending reports")
                    else:
                        self.log_test("Report Filtering by Status", False, f"HTTP {response.status_code}")
                        
                    return True
                else:
                    self.log_test("Report Retrieval", False, "No reports found")
                    return False
            else:
                self.log_test("Report Retrieval", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Report Retrieval", False, f"Error: {str(e)}")
            return False
    
    def test_report_status_management(self):
        """Test report status updates"""
        if not self.created_report_id or not self.created_user_id:
            self.log_test("Report Status Management", False, "No report or user ID available")
            return False
            
        try:
            # Update report status
            data = {
                'new_status': 'in_progress',
                'actor_id': self.created_user_id,
                'note': 'Report assigned to maintenance crew for repair'
            }
            
            response = self.session.patch(f"{API_URL}/reports/{self.created_report_id}/status", data=data)
            if response.status_code == 200:
                result = response.json()
                self.log_test("Status Update", True, result.get("message", "Status updated"))
                
                # Verify status was updated by getting report details
                response = self.session.get(f"{API_URL}/reports/{self.created_report_id}")
                if response.status_code == 200:
                    report_details = response.json()
                    report = report_details.get("report", {})
                    history = report_details.get("history", [])
                    
                    if report.get("status") == "in_progress":
                        self.log_test("Status Verification", True, "Report status correctly updated")
                    else:
                        self.log_test("Status Verification", False, f"Status not updated, still: {report.get('status')}")
                        
                    if len(history) > 0:
                        self.log_test("Status History", True, f"Status history tracked ({len(history)} entries)")
                    else:
                        self.log_test("Status History", False, "No status history found")
                        
                    return True
                else:
                    self.log_test("Status Verification", False, f"Could not retrieve report details: HTTP {response.status_code}")
                    return False
            else:
                self.log_test("Status Update", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Report Status Management", False, f"Error: {str(e)}")
            return False
    
    def test_dashboard_statistics(self):
        """Test dashboard statistics endpoint"""
        try:
            response = self.session.get(f"{API_URL}/dashboard/stats")
            if response.status_code == 200:
                stats = response.json()
                
                required_fields = ["total_reports", "pending_reports", "resolved_reports", "in_progress_reports"]
                missing_fields = [field for field in required_fields if field not in stats]
                
                if not missing_fields:
                    total = stats["total_reports"]
                    pending = stats["pending_reports"]
                    resolved = stats["resolved_reports"]
                    in_progress = stats["in_progress_reports"]
                    
                    self.log_test("Dashboard Statistics", True, 
                                f"Stats: Total={total}, Pending={pending}, Resolved={resolved}, In Progress={in_progress}")
                    
                    # Check for additional data
                    if "recent_resolved" in stats and "high_priority" in stats:
                        recent_count = len(stats["recent_resolved"])
                        high_priority_count = len(stats["high_priority"])
                        self.log_test("Dashboard Additional Data", True, 
                                    f"Recent resolved: {recent_count}, High priority: {high_priority_count}")
                    else:
                        self.log_test("Dashboard Additional Data", False, "Missing recent_resolved or high_priority data")
                        
                    return True
                else:
                    self.log_test("Dashboard Statistics", False, f"Missing required fields: {missing_fields}")
                    return False
            else:
                self.log_test("Dashboard Statistics", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Dashboard Statistics", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("=" * 80)
        print("CIVIC ISSUE REPORTING SYSTEM - BACKEND TESTING")
        print("=" * 80)
        
        tests = [
            ("API Infrastructure", self.test_api_health),
            ("Department System", self.test_department_initialization),
            ("User Management", self.test_user_management),
            ("Report Creation with AI", self.test_report_creation_with_ai),
            ("Report Retrieval", self.test_report_retrieval_and_filtering),
            ("Status Management", self.test_report_status_management),
            ("Dashboard Statistics", self.test_dashboard_statistics)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n--- Testing {test_name} ---")
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ FAIL: {test_name} - Unexpected error: {str(e)}")
                failed += 1
        
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✅ PASSED: {passed}")
        print(f"❌ FAILED: {failed}")
        print(f"📊 SUCCESS RATE: {(passed/(passed+failed)*100):.1f}%")
        
        if failed > 0:
            print("\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   • {result['test']}: {result['message']}")
        
        return passed, failed

if __name__ == "__main__":
    tester = CivicReportingTester()
    passed, failed = tester.run_all_tests()
    
    # Exit with error code if tests failed
    sys.exit(0 if failed == 0 else 1)