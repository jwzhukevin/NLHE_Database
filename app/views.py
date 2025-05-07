# view.py:
# View functions module, handling all user interface related routes and requests
# Includes homepage, material details page, add/edit materials, user authentication, etc.

# Import required modules
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify  # Flask core modules
from flask_login import login_user, logout_user, login_required, current_user  # User authentication modules
from sqlalchemy import and_, or_  # Database query condition builders
from .models import User, Material, BlockedIP  # Custom data models
from . import db  # Database instance
import datetime  # Processing dates and times
import functools  # For decorators
from .material_importer import extract_chemical_formula_from_cif  # Material data import module
import os

# Create a blueprint named 'views' for modular route management
bp = Blueprint('views', __name__)

# Register template filters
@bp.app_template_filter('any')
def any_filter(d):
    """Check if a dictionary has at least one non-empty value (for frontend conditional judgment)
    
    Parameters:
        d: Dictionary to check
    
    Returns: 
        Boolean value indicating whether the dictionary has valid data, used to determine whether to display the reset search button, etc.
    """
    return any(v for v in d.values() if v)

@bp.app_template_filter('remove_key')
def remove_key_filter(d, exclude_key):
    """Generate a new dictionary excluding the specified key (for cleaning search parameters)
    
    Parameters:
        d: Original dictionary
        exclude_key: Key to exclude
    
    Returns: 
        Processed new dictionary, used to build URLs that remove a certain filter condition
    """
    return {k: v for k, v in d.items() if k != exclude_key}

# Landing page route
@bp.route('/')
def landing():
    """Website introduction page - displays website features and functionality overview"""
    return render_template('main/landing.html')

@bp.route('/database')
def index():
    """Material database page - displays material list, supports search, filtering and pagination
    
    Supported GET parameters:
        q: Search keywords
        status: Material status filter
        metal_type: Metal type filter
        formation_energy_min/max: Formation energy range filter
        fermi_level_min/max: Fermi level range filter
        page: Current page number
    """
    # Basic query (get all material records)
    query = Material.query
    
    # Get all search parameters (stored in dictionary for unified processing)
    search_params = {
        'q': request.args.get('q', '').strip(),  # Text search keywords
        'status': request.args.get('status', '').strip(),  # Material status
        'metal_type': request.args.get('metal_type', '').strip(),  # Metal type
        'formation_energy_min': request.args.get('formation_energy_min', '').strip(),  # Formation energy minimum
        'formation_energy_max': request.args.get('formation_energy_max', '').strip(),  # Formation energy maximum
        'fermi_level_min': request.args.get('fermi_level_min', '').strip(),  # Fermi level minimum
        'fermi_level_max': request.args.get('fermi_level_max', '').strip(),  # Fermi level maximum
    }
    
    # Build compound filter conditions (using SQLAlchemy logical operators)
    filters = []
    
    # Text search (supports fuzzy query of name, VBM/CBM coordinates)
    if search_params['q']:
        filters.append(or_(
            Material.name.ilike(f'%{search_params["q"]}%'),  # Name fuzzy matching (case insensitive)
            Material.vbm_coordi.ilike(f'%{search_params["q"]}%'),  # VBM coordinate matching
            Material.cbm_coordi.ilike(f'%{search_params["q"]}%')  # CBM coordinate matching
        ))
    
    # Exact match conditions
    if search_params['status']:
        filters.append(Material.status == search_params['status'])  # Status exact match
    if search_params['metal_type']:
        filters.append(Material.metal_type == search_params['metal_type'])  # Metal type exact match
    
    # Numeric range filtering (including exception handling to ensure valid numerical input)
    for param in ['formation_energy', 'fermi_level']:
        min_val = search_params[f'{param}_min']
        max_val = search_params[f'{param}_max']
        if min_val:
            try:
                filters.append(getattr(Material, param) >= float(min_val))  # Minimum value filter
            except ValueError:  # Handle invalid numerical input
                pass
        if max_val:
            try:
                filters.append(getattr(Material, param) <= float(max_val))  # Maximum value filter
            except ValueError:
                pass
    
    # Apply all filter conditions (using AND logic combination, i.e., all conditions must be met)
    if filters:
        query = query.filter(and_(*filters))
    
    # Pagination configuration (10 records per page)
    page = request.args.get('page', 1, type=int)  # Get current page number, default is page 1
    per_page = 10  # Items per page
    pagination = query.order_by(Material.name.asc()).paginate(  # Sort by name in ascending order
        page=page, 
        per_page=per_page, 
        error_out=False  # Disable invalid page number errors, out of range will return empty list
    )
    
    # Render template and pass pagination object and search parameters
    return render_template('main/index.html',
                         materials=pagination.items,  # Current page data
                         pagination=pagination,  # Pagination object (including page number information)
                         search_params=search_params)  # Search parameters (for form display)

# Define an admin check decorator
def admin_required(view_func):
    """
    Decorator to restrict route access to admin users only
    
    If user is not authenticated or not an admin, redirect to login page
    """
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied. This feature requires administrator privileges.', 'error')
            return redirect(url_for('views.login'))
        
        return view_func(*args, **kwargs)
    
    return wrapped_view

# Material add route (admin required)
@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    """
    Page and processing logic for adding new material records
    
    GET request: Display add material form
    POST request: Process form submission, add new material to database
    """
    if request.method == 'POST':
        try:
            # Get and process uploaded files
            structure_file = request.files.get('structure_file')
            band_file = request.files.get('band_file')
            properties_json = request.files.get('properties_json')
            sc_structure_file = request.files.get('sc_structure_file')
            
            # Validate if the CIF file is valid
            if not structure_file or not structure_file.filename.endswith('.cif'):
                flash('Please upload a valid CIF file!', 'error')
                return redirect(url_for('views.add'))
            
            # Generate safe filenames and save structure files
            from werkzeug.utils import secure_filename
            import os
            from flask import current_app
            
            # First save the structure file to a temporary location for extracting the chemical formula
            structure_filename = secure_filename(structure_file.filename)
            temp_structure_path = os.path.join(current_app.root_path, 'static/temp', structure_filename)
            os.makedirs(os.path.dirname(temp_structure_path), exist_ok=True)
            structure_file.save(temp_structure_path)
            
            # Extract chemical formula from CIF file
            chemical_name = extract_chemical_formula_from_cif(temp_structure_path)
            
            # Verify if the material name was successfully extracted
            if not chemical_name:
                flash('Unable to extract material name from CIF file, please check the file format', 'error')
                return redirect(url_for('views.add'))
            
            # Verify if the material name already exists
            if Material.query.filter_by(name=chemical_name).first():
                flash(f'Material name "{chemical_name}" already exists, please use a different CIF file', 'error')
                return redirect(url_for('views.add'))
            
            # Create material object and add to database to get ID
            material_data = {
                'name': chemical_name,  # Use chemical formula extracted from CIF
                'status': request.form.get('status'),  # Status
                'structure_file': structure_filename,  # Structure file path
                'properties_json': properties_json.filename if properties_json and properties_json.filename else None,
                'sc_structure_file': sc_structure_file.filename if sc_structure_file and sc_structure_file.filename else None,
                'total_energy': safe_float(request.form.get('total_energy')),
                'formation_energy': safe_float(request.form.get('formation_energy')),
                'fermi_level': safe_float(request.form.get('efermi')),  # Match form field name 'efermi'
                'vacuum_level': safe_float(request.form.get('vacuum_level')),
                'workfunction': safe_float(request.form.get('workfunction')),
                'metal_type': request.form.get('metal_type'),
                'gap': safe_float(request.form.get('gap')),
                'vbm_energy': safe_float(request.form.get('vbm_energy')),
                'cbm_energy': safe_float(request.form.get('cbm_energy')),
                'vbm_coordi': request.form.get('vbm_coordi'),
                'cbm_coordi': request.form.get('cbm_coordi'),
                'vbm_index': safe_int(request.form.get('vbm_index')),
                'cbm_index': safe_int(request.form.get('cbm_index'))
            }

            # Create Material object and validate data
            material = Material(**material_data)
            material.validate()  # Call model custom validation method to check data integrity
            
            # First add to database to get ID
            db.session.add(material)
            db.session.flush()  # Get ID but don't commit transaction

            # Format ID (IMR-00000XXX)
            formatted_id = f"IMR-{material.id:08d}"
            
            # Create material-specific folder structure
            material_dir = os.path.join(current_app.root_path, 'static/materials', formatted_id)
            structure_dir = os.path.join(material_dir, 'structure')
            band_dir = os.path.join(material_dir, 'band')
            bcd_dir = os.path.join(material_dir, 'bcd')
            
            # Create all directories
            os.makedirs(material_dir, exist_ok=True)
            os.makedirs(structure_dir, exist_ok=True)
            os.makedirs(band_dir, exist_ok=True)
            os.makedirs(bcd_dir, exist_ok=True)
            
            # Save CIF file to structure folder
            structure_path = os.path.join(structure_dir, structure_filename)
            os.rename(temp_structure_path, structure_path)
            
            # Process JSON properties file
            if properties_json and properties_json.filename:
                properties_json_filename = secure_filename(properties_json.filename)
                properties_json_path = os.path.join(material_dir, properties_json_filename)
                properties_json.save(properties_json_path)
                material.properties_json = properties_json_filename
            else:
                # Create JSON file with necessary fields, not an empty JSON object
                import json
                json_data = {
                  "name": chemical_name,
                  "status": request.form.get('status') or "pending",
                  "structure_file": structure_filename,
                  "total_energy": material.total_energy,
                  "formation_energy": material.formation_energy,
                  "fermi_level": material.fermi_level,
                  "vacuum_level": material.vacuum_level,
                  "workfunction": material.workfunction,
                  "metal_type": material.metal_type or "No Data",
                  "gap": material.gap,
                  "vbm_energy": material.vbm_energy,
                  "cbm_energy": material.cbm_energy,
                  "vbm_coordi": material.vbm_coordi or "No Data",
                  "cbm_coordi": material.cbm_coordi or "No Data",
                  "vbm_index": material.vbm_index,
                  "cbm_index": material.cbm_index
                }
                json_file_path = os.path.join(material_dir, 'material.json')
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                material.properties_json = 'material.json'
            
            # Process band dat file
            if band_file and band_file.filename.endswith('.dat'):
                band_filename = secure_filename(band_file.filename)
                band_path = os.path.join(band_dir, band_filename)
                band_file.save(band_path)
            
            # Process SC structure dat file
            if sc_structure_file and sc_structure_file.filename.endswith('.dat'):
                sc_filename = secure_filename(sc_structure_file.filename)
                sc_path = os.path.join(bcd_dir, sc_filename)
                sc_structure_file.save(sc_path)
            
            # Also save to regular folder to maintain backward compatibility
            if band_file and band_file.filename:
                band_path = os.path.join(current_app.root_path, 'static/band', secure_filename(band_file.filename))
                os.makedirs(os.path.dirname(band_path), exist_ok=True)
                # Create symlink instead of copying to prevent duplicate storage
                try:
                    os.symlink(os.path.join(band_dir, secure_filename(band_file.filename)), band_path)
                except:
                    import shutil
                    shutil.copy2(os.path.join(band_dir, secure_filename(band_file.filename)), band_path)
            
            # Commit database transaction
            db.session.commit()
            
            flash(f'Material added successfully. Data has been synchronized to the {formatted_id} folder.', 'success')
            return redirect(url_for('views.index'))  # Redirect to homepage

        except ValueError as e:  # Handle data type errors
            flash(f'Invalid data: {str(e)}', 'error')  # Display detailed error message
            return redirect(url_for('views.add'))
        except Exception as e:  # Handle other database errors
            db.session.rollback()  # Rollback transaction, discard all changes
            flash(f'An error occurred: {str(e)}', 'error')  # Display general error message
            return redirect(url_for('views.add'))

    return render_template('materials/add.html')  # GET request returns form page

# Safe numeric conversion helper functions
def safe_float(value):
    """Safely convert string to float (allows empty values)
    
    Parameters:
        value: Input string
    
    Returns: 
        float or None, returns None if conversion fails or input is empty
    """
    try:
        return float(value) if value else None
    except ValueError:
        return None

def safe_int(value):
    """Safely convert string to integer (allows empty values)
    
    Parameters:
        value: Input string
    
    Returns: 
        int or None, returns None if conversion fails or input is empty
    """
    try:
        return int(value) if value else None
    except ValueError:
        return None

# Material edit route (admin required)
@bp.route('/materials/edit/IMR-<string:material_id>', methods=['GET', 'POST'])
@login_required  
@admin_required
def edit(material_id):
    """
    Edit existing material record
    
    GET request: Display edit form, pre-fill current data
    POST request: Process form submission, update database record
    
    Parameters:
        material_id: ID of the material to edit (format is number part, no IMR-prefix)
    """
    # Extract numeric part from string ID
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
        
    # Query material record to edit
    material = Material.query.get_or_404(numeric_id)  # Get material or return 404
    
    if request.method == 'POST':
        try:
            # Process structure file update
            structure_file = request.files.get('structure_file')
            band_file = request.files.get('band_file')
            properties_json = request.files.get('properties_json')
            sc_structure_file = request.files.get('sc_structure_file')
            
            # If a new structure file is uploaded
            if structure_file and structure_file.filename:
                if not structure_file.filename.endswith('.cif'):
                    flash('Please upload a valid CIF file!', 'error')
                    return redirect(url_for('views.edit', material_id=material_id))
                
                # Save new structure file
                from werkzeug.utils import secure_filename
                import os
                structure_filename = secure_filename(structure_file.filename)
                structure_path = os.path.join(current_app.root_path, 'static/structures', structure_filename)
                os.makedirs(os.path.dirname(structure_path), exist_ok=True)
                structure_file.save(structure_path)
                material.structure_file = structure_filename
                
                # Extract chemical formula from CIF file
                chemical_name = extract_chemical_formula_from_cif(structure_path)
                if chemical_name:
                    # Check if new name conflicts with other materials (excluding current material)
                    existing_material = Material.query.filter(
                        Material.name == chemical_name,
                        Material.id != numeric_id
                    ).first()
                    
                    if existing_material:
                        flash(f'Material name "{chemical_name}" already exists, please use a different CIF file', 'error')
                        return redirect(url_for('views.edit', material_id=material_id))
                    
                    # Update material name
                    material.name = chemical_name
                    flash(f'Material name has been updated from CIF file: {chemical_name}', 'info')
            
            # Process attribute JSON file
            if properties_json and properties_json.filename:
                properties_json_filename = secure_filename(properties_json.filename)
                properties_json_path = os.path.join(current_app.root_path, 'static/properties', properties_json_filename)
                os.makedirs(os.path.dirname(properties_json_path), exist_ok=True)
                properties_json.save(properties_json_path)
                material.properties_json = properties_json_filename
            
            # Process SC structure file
            if sc_structure_file and sc_structure_file.filename:
                sc_structure_filename = secure_filename(sc_structure_file.filename)
                sc_structure_path = os.path.join(current_app.root_path, 'static/sc_structures', sc_structure_filename)
                os.makedirs(os.path.dirname(sc_structure_path), exist_ok=True)
                sc_structure_file.save(sc_structure_path)
                material.sc_structure_file = sc_structure_filename
            
            # Process band file update
            if band_file and band_file.filename:
                if band_file.filename.endswith(('.json', '.dat')):
                    band_filename = secure_filename(band_file.filename)
                    band_path = os.path.join(current_app.root_path, 'static/band', band_filename)
                    os.makedirs(os.path.dirname(band_path), exist_ok=True)
                    band_file.save(band_path)
            
            # Update other material attributes (only use form name if no new CIF file is uploaded)
            if not structure_file or not structure_file.filename or not material.name:
                material.name = request.form.get('name')
            
            # Verify name is not empty
            if not material.name:
                flash('Material name cannot be empty!', 'error')
                return redirect(url_for('views.edit', material_id=material_id))
            
            # Update other material attributes
            material.status = request.form.get('status')
            material.total_energy = safe_float(request.form.get('total_energy'))
            material.formation_energy = safe_float(request.form.get('formation_energy'))
            material.fermi_level = safe_float(request.form.get('efermi'))  # Changed to match form field name
            material.vacuum_level = safe_float(request.form.get('vacuum_level'))
            material.workfunction = safe_float(request.form.get('workfunction'))
            material.metal_type = request.form.get('metal_type')
            material.gap = safe_float(request.form.get('gap'))
            material.vbm_energy = safe_float(request.form.get('vbm_energy'))
            material.cbm_energy = safe_float(request.form.get('cbm_energy'))
            material.vbm_coordi = request.form.get('vbm_coordi')
            material.cbm_coordi = request.form.get('cbm_coordi')
            material.vbm_index = safe_int(request.form.get('vbm_index'))
            material.cbm_index = safe_int(request.form.get('cbm_index'))
            
            # Save changes
            db.session.commit()
            flash('Material updated successfully.', 'success')
            return redirect(url_for('views.detail', material_id=material_id))
            
        except ValueError as e:
            flash(f'Invalid data: {str(e)}', 'error')
            return redirect(url_for('views.edit', material_id=material_id))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('views.edit', material_id=material_id))
    
    # GET request: Display edit form
    return render_template('materials/edit.html', material=material)

# Material detail page
@bp.route('/materials/IMR-<string:material_id>')
def detail(material_id):
    """
    Display page showing detailed information about a material
    
    Parameters:
        material_id: ID of the material to display (format is number part, no IMR-prefix)
    
    Returns:
        Rendered detail page template, containing material data and structure file path
    """
    # Extract numeric part from string ID
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
    
    # Get material from database, return 404 if not found
    material = Material.query.get_or_404(numeric_id)
    
    # If needed, here you can add logic to update material data from JSON file
    # For example: If material status is "Need Update", automatically refresh data from JSON
    
    # Build structure file path - first try new directory structure
    # Format ID (IMR-00000XXX)
    formatted_id = f"IMR-{numeric_id:08d}"
    structure_file = None
    
    # Check if new directory structure contains structure file
    new_structure_path = f'materials/{formatted_id}/structure/structure.cif'
    if os.path.exists(os.path.join(current_app.root_path, 'static', new_structure_path)):
        structure_file = new_structure_path
    # If new directory structure does not find, try old directory structure
    elif material.structure_file:
        old_structure_path = f'structures/{material.structure_file}'
        if os.path.exists(os.path.join(current_app.root_path, 'static', old_structure_path)):
            structure_file = old_structure_path
    
    # Render detail page template
    return render_template('materials/detail.html', 
                          material=material,
                          structure_file=structure_file)

# Material delete route (admin required)
@bp.route('/materials/delete/IMR-<string:material_id>', methods=['POST'])
@login_required  
@admin_required
def delete(material_id):
    """
    Delete material record
    
    Parameters:
        material_id: ID of the material to delete (format is number part, no IMR-prefix)
    
    Note:
        Only accepts POST requests, to prevent CSRF attacks
    """
    # Extract numeric part from string ID
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
        
    material = Material.query.get_or_404(numeric_id)  # Get material or return 404 error
    
    # Delete related files
    import os
    import shutil
    from flask import current_app
    
    # Format ID (IMR-00000XXX)
    formatted_id = f"IMR-{numeric_id:08d}"
    
    # Delete material-specific folder and all its contents
    material_dir = os.path.join(current_app.root_path, 'static/materials', formatted_id)
    if os.path.exists(material_dir):
        shutil.rmtree(material_dir)
    
    # Keep original file deletion logic to ensure backward compatibility
    # Delete structure file
    if material.structure_file:
        structure_path = os.path.join(current_app.root_path, 'static/structures', material.structure_file)
        if os.path.exists(structure_path):
            os.remove(structure_path)
    
    # Delete band file
    band_path = os.path.join(current_app.root_path, 'static/band', f'{material.id}.dat')
    if os.path.exists(band_path):
        os.remove(band_path)
    
    # Delete attribute JSON file
    if material.properties_json:
        json_path = os.path.join(current_app.root_path, 'static/properties', material.properties_json)
        if os.path.exists(json_path):
            os.remove(json_path)
    
    # Delete SC structure file
    if material.sc_structure_file:
        sc_path = os.path.join(current_app.root_path, 'static/sc_structures', material.sc_structure_file)
        if os.path.exists(sc_path):
            os.remove(sc_path)
    
    db.session.delete(material)  # Delete record
    db.session.commit()  # Commit transaction
    flash(f'Material "{material.name}" and all related files have been successfully deleted.', 'success')  # Display success message
    return redirect(url_for('views.index'))  # Redirect to homepage

# Helper function to get client IP
def get_client_ip():
    """Get client IP address of the current request
    
    Returns: 
        String representing client IP address
    """
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.remote_addr

# IP block check decorator
def check_ip_blocked(view_func):
    """Decorator to check if IP is blocked
    
    If IP is blocked, redirect to homepage and display warning message
    """
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        client_ip = get_client_ip()
        
        # Check if IP is in blocked list
        blocked = BlockedIP.query.filter_by(ip_address=client_ip).first()
        if blocked:
            flash('Access denied. Your IP has been blocked due to multiple failed login attempts.', 'error')
            return redirect(url_for('views.landing'))
        
        return view_func(*args, **kwargs)
    
    return wrapped_view

# User login route
@bp.route('/login', methods=['GET', 'POST'])
@check_ip_blocked  # Apply IP block check decorator
def login():
    """
    User login page and processing logic
    
    GET request: Display login form
    POST request: Verify credentials and execute login, track failed login attempts
    """
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        username = request.form['username'].strip()
        password = request.form['password']
        login_type = request.form.get('login_type', 'user')
        client_ip = get_client_ip()
        
        # Use session to store login attempt count
        if 'login_attempts' not in session:
            session['login_attempts'] = 0
        
        if not email or not username or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('views.login'))
        
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists
        if not user:
            session['login_attempts'] += 1
            current_attempts = session['login_attempts']
            
            if current_attempts >= 5:
                blocked_ip = BlockedIP(
                    ip_address=client_ip,
                    blocked_at=datetime.datetime.now(),
                    reason="Multiple failed login attempts"
                )
                db.session.add(blocked_ip)
                db.session.commit()
                session.pop('login_attempts', None)
                flash('Your IP has been blocked due to too many failed login attempts.', 'error')
                return redirect(url_for('views.landing'))
            
            remaining_attempts = 5 - current_attempts
            flash(f'Invalid credentials. You have {remaining_attempts} attempts remaining before being blocked.', 'error')
            return redirect(url_for('views.login'))
        
        # Check if login_type is admin but user role is not admin
        if login_type == 'admin' and user.role != 'admin':
            session['login_attempts'] += 1
            current_attempts = session['login_attempts']
            
            if current_attempts >= 3:
                blocked_ip = BlockedIP(
                    ip_address=client_ip,
                    blocked_at=datetime.datetime.now(),
                    reason="Unauthorized admin login attempts"
                )
                db.session.add(blocked_ip)
                db.session.commit()
                session.pop('login_attempts', None)
                flash('Your IP has been blocked due to unauthorized admin login attempts.', 'error')
                return redirect(url_for('views.landing'))
            
            remaining_attempts = 3 - current_attempts
            flash(f'Invalid administrator credentials. You have {remaining_attempts} attempts remaining before being blocked.', 'error')
            return redirect(url_for('views.login'))
        
        # For regular user login, verify username, password
        if user.username != username or not user.validate_password(password):
            session['login_attempts'] += 1
            current_attempts = session['login_attempts']
            
            if current_attempts >= 5:
                blocked_ip = BlockedIP(
                    ip_address=client_ip,
                    blocked_at=datetime.datetime.now()
                )
                db.session.add(blocked_ip)
                db.session.commit()
                session.pop('login_attempts', None)
                flash('Your IP has been blocked due to too many failed login attempts.', 'error')
                return redirect(url_for('views.landing'))
            
            remaining_attempts = 5 - current_attempts
            flash(f'Invalid credentials. You have {remaining_attempts} attempts remaining before being blocked.', 'error')
            return redirect(url_for('views.login'))
        
        # Login successful, reset attempt count
        session.pop('login_attempts', None)
        login_user(user)
        flash(f'Login successful as {"Administrator" if user.role == "admin" else "User"}.', 'success')
        return redirect(url_for('views.index'))
        
    return render_template('auth/login.html')

# User logout route
@bp.route('/logout')
@login_required  # Login protection decorator, ensuring only logged-in users can logout
def logout():
    """
    Handle user logout
    
    Perform logout operation and redirect to homepage
    """
    logout_user()  # Flask-Login logout method, clear user session
    flash('Goodbye.', 'info')  # Display information message
    return redirect(url_for('views.index'))  # Redirect to homepage

# User settings route
@bp.route('/settings', methods=['GET', 'POST'])
@login_required  # Login protection decorator
def settings():
    """
    User settings page and processing logic
    
    GET request: Display settings form
    POST request: Update user settings
    """
    if request.method == 'POST':
        username = request.form['username'].strip()
        name = request.form['name'].strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate inputs
        if not username or not name:
            flash('Username and display name are required.', 'error')
            return redirect(url_for('views.settings'))
        
        if len(username) > 20 or len(name) > 20:
            flash('Username and display name must be 20 characters or less.', 'error')
            return redirect(url_for('views.settings'))
        
        # Check if another user already has this username (except current user)
        existing_user = User.query.filter(User.username == username, User.email != current_user.email).first()
        if existing_user:
            flash('This username is already taken. Please choose another.', 'error')
            return redirect(url_for('views.settings'))
        
        changes_made = False
        
        # Check if username or name changed
        if username != current_user.username or name != current_user.name:
            current_app.logger.info(f"Updating user {current_user.email} profile: username={username}, name={name}")
            current_user.username = username
            current_user.name = name
            changes_made = True
        
        # Password change logic
        if new_password:
            # Verify current password
            if not current_user.validate_password(current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('views.settings'))
            
            # Validate new password
            if len(new_password) < 8:
                flash('New password must be at least 8 characters long.', 'error')
                return redirect(url_for('views.settings'))
            
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('views.settings'))
            
            # Set new password
            current_app.logger.info(f"Updating password for user {current_user.email}")
            current_user.set_password(new_password)
            
            # 单独保存密码到文件系统中
            save_user_password(current_user.email, new_password)
            changes_made = True
        
        if not changes_made:
            flash('No changes were made.', 'info')
            return redirect(url_for('views.settings'))
            
        try:
            # Commit database changes
            db.session.commit()
            current_app.logger.info(f"Successfully updated user {current_user.email} in database")
            
            # Update users.dat file with the latest user data
            update_users_dat()
            flash('Settings updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating user settings: {str(e)}")
            flash(f'An error occurred while saving settings: {str(e)}', 'error')
            
        return redirect(url_for('views.index'))
    
    return render_template('auth/settings.html', user=current_user)

# Helper function to save user password
def save_user_password(user_email, new_password):
    """
    直接保存单个用户的密码，以避免users.dat文件处理的复杂性
    
    Parameters:
        user_email: 用户邮箱（作为唯一标识）
        new_password: 用户新密码（将被加密存储）
    """
    try:
        users_dir = os.path.join(current_app.root_path, 'static/users')
        os.makedirs(users_dir, exist_ok=True)
        
        # 替换特殊字符，生成安全的文件名
        safe_email = user_email.replace('@', '_at_').replace('.', '_dot_')
        password_file = os.path.join(users_dir, f"{safe_email}.pwd")
        
        # 记录用户密码变更操作
        current_app.logger.info(f"Saving password for user {user_email}")
        
        # 写入密码到用户特定的文件
        with open(password_file, 'w') as f:
            f.write(new_password)
            
        current_app.logger.info(f"Password for {user_email} saved successfully")
        return True
    except Exception as e:
        current_app.logger.error(f"Error saving password for {user_email}: {str(e)}")
        return False

# Helper function to update users.dat file
def update_users_dat():
    """Update users.dat file with latest user information"""
    users_file = os.path.join(current_app.root_path, 'static/users/users.dat')
    current_app.logger.info(f"Updating users file at: {users_file}")
    
    # Get all users from database
    users = User.query.all()
    current_app.logger.info(f"Found {len(users)} users to update")
    
    # Create backup of original file
    backup_file = f"{users_file}.bak"
    if os.path.exists(users_file):
        import shutil
        shutil.copy2(users_file, backup_file)
        current_app.logger.info(f"Created backup at: {backup_file}")
    
    # Create directory if it doesn't exist
    users_dir = os.path.dirname(users_file)
    os.makedirs(users_dir, exist_ok=True)
    current_app.logger.info(f"Ensured directory exists: {users_dir}")
    
    # Read existing users.dat file to preserve passwords
    existing_passwords = {}
    if os.path.exists(users_file):
        try:
            with open(users_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(':')
                    if len(parts) >= 4:
                        email, username, password, role = parts[0], parts[1], parts[2], parts[3]
                        existing_passwords[email] = password
                        current_app.logger.debug(f"Read existing password for {email}")
        except Exception as e:
            current_app.logger.error(f"Error reading users.dat: {str(e)}")
    else:
        current_app.logger.warning(f"users.dat file does not exist at {users_file}")
    
    # 尝试从单独的密码文件中读取密码
    for user in users:
        if user.email not in existing_passwords:
            try:
                safe_email = user.email.replace('@', '_at_').replace('.', '_dot_')
                password_file = os.path.join(users_dir, f"{safe_email}.pwd")
                if os.path.exists(password_file):
                    with open(password_file, 'r') as f:
                        existing_passwords[user.email] = f.read().strip()
                        current_app.logger.debug(f"Read password from file for {user.email}")
            except Exception as e:
                current_app.logger.error(f"Error reading password file for {user.email}: {str(e)}")
    
    # Write updated user data to file
    try:
        with open(users_file, 'w') as f:
            f.write("# Format: email:username:password:role\n")
            f.write("# Available roles: admin, user\n")
            f.write("# One user per line\n")
            
            for user in users:
                # Get password from existing file or use default
                password = existing_passwords.get(user.email, "password123")
                
                line = f"{user.email}:{user.username}:{password}:{user.role}\n"
                f.write(line)
                current_app.logger.debug(f"Wrote user data for {user.email}")
        
        current_app.logger.info(f"Successfully updated users.dat file with {len(users)} users")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to write users.dat file: {str(e)}")
        raise