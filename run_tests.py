#!/usr/bin/env python3
"""
Test runner for MyTypist Backend
This script can be run independently to test the application
"""

import sys
import os
import subprocess
import platform

def find_python():
    """Find available Python executable"""
    import shutil
    python_commands = ['python', 'python3', 'py']

    if platform.system() == 'Windows':
        python_commands.extend(['python.exe', 'python3.exe'])

    for cmd in python_commands:
        try:
            # Use shutil.which to get full path and validate it exists
            python_path = shutil.which(cmd)
            if not python_path:
                continue
            
            # Basic path validation - ensure it's in expected system directories
            if platform.system() == 'Windows':
                safe_paths = ['python', 'anaconda', 'miniconda', 'program files']
            else:
                safe_paths = ['/usr/', '/opt/', '/home/', '/.pyenv/', '/Library/']
            
            # Allow if path contains expected directory patterns
            path_lower = python_path.lower()
            if not any(safe_path in path_lower for safe_path in safe_paths):
                print(f"Skipping Python at suspicious path: {python_path}")
                continue
            
            result = subprocess.run([python_path, '--version'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            if result.returncode == 0:
                print(f"Found Python: {python_path} - {result.stdout.strip()}")
                return python_path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return None

def install_dependencies(python_cmd):
    """Install required dependencies"""
    print("Installing dependencies...")

    try:
        # Try pip install
        result = subprocess.run([
            python_cmd, '-m', 'pip', 'install',
            'pytest', 'pytest-asyncio', 'httpx', 'fastapi', 'sqlalchemy'
        ], capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
            return True
        else:
            print(f"❌ Dependency installation failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Could not install dependencies: {e}")
        return False

def run_tests(python_cmd):
    """Run the test suite"""
    print("Running tests...")

    # Change to the correct directory
    os.chdir(os.path.dirname(__file__))

    try:
        # Run pytest
        result = subprocess.run([
            python_cmd, '-m', 'pytest',
            'app/tests/',
            '-v',
            '--tb=short',
            '-x'  # Stop on first failure
        ], timeout=300)

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("❌ Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

def run_basic_validation():
    """Run basic validation without external dependencies"""
    print("Running basic validation...")

    # Test import capabilities
    try:
        sys.path.append(os.path.dirname(__file__))

        # Test configuration
        from config import settings
        print(f"✅ Configuration loaded: {settings.APP_NAME} v{settings.APP_VERSION}")

        # Test database module
        from database import DatabaseManager
        print("✅ Database module loaded")

        # Test models
        from app.models.user import User, UserRole, UserStatus
        print("✅ User model loaded")

        # Test that enums work
        assert len(list(UserRole)) > 0
        assert len(list(UserStatus)) > 0
        print("✅ Enums validated")

        # Test services
        from app.services.auth_service import AuthService
        print("✅ Auth service loaded")

        print("✅ Basic validation passed!")
        return True

    except Exception as e:
        print(f"❌ Basic validation failed: {e}")
        return False

def main():
    """Main test runner"""
    print("🧪 MyTypist Backend Test Runner")
    print("=" * 50)

    # First try basic validation
    if not run_basic_validation():
        print("\n❌ Basic validation failed. Please check imports and dependencies.")
        return 1

    # Try to find Python
    python_cmd = find_python()

    if not python_cmd:
        print("\n⚠️  Python not found in PATH")
        print("Basic validation passed, but cannot run full test suite")
        print("Please ensure Python is installed and available in PATH")
        return 1

    # Try to install dependencies
    if not install_dependencies(python_cmd):
        print("\n⚠️  Could not install test dependencies")
        print("Please install manually: pip install pytest pytest-asyncio httpx")
        return 1

    # Run tests
    if run_tests(python_cmd):
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
