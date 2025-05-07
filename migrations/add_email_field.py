import os
import sys
import sqlite3
import random
import string

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the application
from app import create_app, db
from app.models import User

def generate_random_email(username):
    """Generate a random email address for a user"""
    domains = ['example.com', 'email.com', 'test.org', 'mail.net', 'university.edu']
    domain = random.choice(domains)
    return f"{username}@{domain}"

def migrate_database():
    """Add email field to User model and generate unique email for existing users"""
    app = create_app()
    
    with app.app_context():
        print("Starting database migration...")
        
        # Check if email column already exists
        try:
            conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(user)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'email' in columns:
                print("Email column already exists. Skipping migration.")
                return
            
            # Add email column to user table
            print("Adding email column to user table...")
            cursor.execute("ALTER TABLE user ADD COLUMN email TEXT")
            cursor.execute("ALTER TABLE user ADD COLUMN verification_code TEXT")
            cursor.execute("ALTER TABLE user ADD COLUMN code_expiry TIMESTAMP")
            conn.commit()
            
            # Fetch all users
            users = User.query.all()
            print(f"Found {len(users)} users to migrate.")
            
            # Generate and assign unique emails
            email_dict = {}
            for user in users:
                # Generate a unique email for each user
                base_email = generate_random_email(user.username)
                email = base_email
                
                # Ensure email is unique
                counter = 1
                while email in email_dict:
                    email = f"{user.username}{counter}@{base_email.split('@')[1]}"
                    counter += 1
                
                email_dict[email] = user.username
                
                # Update user email in database
                print(f"Assigning email {email} to user {user.username}")
                cursor.execute("UPDATE user SET email = ? WHERE id = ?", (email, user.id))
            
            # Make email column not nullable and unique
            print("Setting email column constraints...")
            conn.execute("CREATE UNIQUE INDEX idx_user_email ON user(email)")
            conn.commit()
            
            # Update users.dat file format
            update_users_dat(app, email_dict)
            
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"Error during migration: {str(e)}")
            conn.rollback()
            raise
        finally:
            conn.close()

def update_users_dat(app, email_dict):
    """Update users.dat file to include email field"""
    users_file = os.path.join(app.root_path, 'static/users/users.dat')
    
    if not os.path.exists(users_file):
        print(f"Warning: users.dat file not found at {users_file}")
        return
    
    print(f"Updating users.dat file at {users_file}...")
    
    # Create backup
    backup_file = f"{users_file}.bak"
    import shutil
    shutil.copy2(users_file, backup_file)
    
    # Read existing users
    users = []
    with open(users_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                users.append(line)
                continue
            
            parts = line.split(':')
            if len(parts) < 3:
                users.append(line)  # Keep invalid lines as-is
                continue
            
            username, password, role = parts[0], parts[1], parts[2]
            
            # Find corresponding email or generate new one
            email = None
            for e, u in email_dict.items():
                if u == username:
                    email = e
                    break
            
            if not email:
                email = generate_random_email(username)
            
            # Create new line with email
            users.append(f"{email}:{username}:{password}:{role}")
    
    # Update file header
    header = [
        "# Format: email:username:password:role",
        "# Available roles: admin, user",
        "# One user per line"
    ]
    
    # Write updated file
    with open(users_file, 'w') as f:
        # Write header
        for line in header:
            f.write(f"{line}\n")
        
        # Write user lines (skip any existing header lines)
        for line in users:
            if not line.startswith('#'):
                f.write(f"{line}\n")
    
    print("users.dat file updated successfully!")

if __name__ == "__main__":
    migrate_database() 