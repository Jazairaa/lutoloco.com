
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For session management and flashing messages

# Database Configuration
db_config = {
    'host': 'localhost',  # Update with your database host
    'user': 'root',       # Update with your database username
    'password': '',       # Update with your database password
    'database': 'lutoloco'  # Update with your database name
}

def connect_db():
    """Establishes a connection to the database."""
    try:
        return mysql.connector.connect(**db_config)
    except Error as err:
        print(f"Error connecting to database: {err}")
        return None
    

@app.route('/register', methods=['GET', 'POST'])
def register():
    errors = {}
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Field validation
        if not username:
            errors['username'] = 'Username is required'
        
        if not password:
            errors['password'] = 'Password is required'
        elif len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters'

        if not confirm_password:
            errors['confirm_password'] = 'Please confirm your password'
        elif password != confirm_password:
            errors['confirm_password'] = 'Passwords do not match'

        # If there are no errors, proceed with registration
        if not errors:
            conn = connect_db()
            if not conn:
                flash('Database connection error', 'error')
                return redirect(url_for('register'))

            try:
                cursor = conn.cursor()
                # Check existing username
                cursor.execute("SELECT * FROM user WHERE username = %s", (username,))
                if cursor.fetchone():
                    errors['username'] = 'Username already taken'
                else:
                    # Insert new user
                    cursor.execute("INSERT INTO user (username, password) VALUES (%s, %s)",
                                 (username, password))
                    conn.commit()
                    flash('Registration successful!', 'success')
                    return redirect(url_for('login'))
            finally:
                cursor.close()
                conn.close()

        # If there are errors, re-render the form with error messages
        return render_template('register.html', errors=errors)

    return render_template('register.html', errors={})

@app.route('/', methods=['GET', 'POST'])
def login():
    errors = {}
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Field validation
        if not username:
            errors['username'] = 'Username is required'
        
        if not password:
            errors['password'] = 'Password is required'

        # If there are no errors, proceed with login
        if not errors:
            conn = connect_db()
            if not conn:
                flash('Database connection error', 'error')
                return redirect(url_for('login'))

            try:
                cursor = conn.cursor()
                
                # Admin login check
                if username == "admin" and password == "admin123":
                    session['username'] = username
                    return redirect(url_for('admin_manage_recipe'))

                # Regular user login check
                cursor.execute("SELECT username, password FROM user WHERE username = %s", 
                             (username,))
                user = cursor.fetchone()

                if not user:
                    errors['username'] = 'Username not found'
                elif user[1] != password:
                    errors['password'] = 'Incorrect password'
                else:
                    session['username'] = username
                    return redirect(url_for('main_dashboard'))
            finally:
                cursor.close()
                conn.close()

        # If there are errors, re-render the form with error messages
        return render_template('login.html', errors=errors)

    return render_template('login.html', errors={})

@app.route('/main_dashboard')
def main_dashboard():
    if 'username' not in session:
        flash('You must log in to access the dashboard.', 'error')
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    username = session['username']
    conn = connect_db()
    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor()

    try:
        cursor.execute("SELECT category, name, image_url, time FROM recipe")
        recipe = cursor.fetchall()
        conn.close()

        return render_template('main_dashboard.html', username=username, recipe=recipe)

    except Exception as e:
        flash(f"Error: {e}", 'error')
        conn.close()
        return redirect(url_for('login'))

@app.route('/recipes')
def recipe():
    # Connect to the database
    conn = connect_db()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('main_dashboard'))  # Redirect to dashboard if DB fails

    cursor = conn.cursor(dictionary=True)  # Use dictionary cursor for easier processing

    try:
        # Fetch all recipes with their categories
        query = "SELECT category, name, image_url, time FROM recipe ORDER BY category"
        cursor.execute(query)
        recipes = cursor.fetchall()

        # Group recipes by category
        categorized_recipes = {}
        for recipe in recipes:
            category = recipe['category']
            if category not in categorized_recipes:
                categorized_recipes[category] = []
            categorized_recipes[category].append(recipe)

        return render_template('recipe.html', categorized_recipes=categorized_recipes)

    except Exception as e:
        flash(f"Error fetching recipes: {e}", 'error')
        return redirect(url_for('main_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/favorite_list', methods=['GET'])
def favorite_list():
    """Display the user's favorite recipes."""
    if 'username' not in session:
        flash('You must log in to view your favorite list.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    conn = connect_db()

    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('main_dashboard'))

    cursor = conn.cursor()

    try:
        # Fetch user ID
        cursor.execute("SELECT id FROM user WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", 'error')
            return redirect(url_for('login'))

        user_id = user[0]

        # Fetch the user's favorite recipes
        cursor.execute("""
            SELECT r.id, r.name, r.category, r.image_url 
            FROM recipe r
            JOIN favorite f ON r.id = f.recipe_id
            
            WHERE f.user_id = %s
        """, (user_id,))
        favorite_recipes = cursor.fetchone()

        # Notify if no favorites are found
        if not favorite_list:
            flash("No favorite recipes found.", 'info')

        return render_template('favorite_list', favorite_list=favorite_recipes)

    except Exception as e:
        app.logger.error(f"Error fetching favorites: {e}")
        flash("An error occurred while fetching your favorites.", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/add_to_favorites/<int:recipe_id>', methods=['POST'])
def add_to_favorites(recipe_id):
    """Add a recipe to the user's favorites."""
    if 'username' not in session:
        flash('You must log in to add to your favorites.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    conn = connect_db()

    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('main_dashboard'))

    cursor = conn.cursor()

    try:
        # Fetch user ID
        cursor.execute("SELECT id FROM user WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", 'error')
            return redirect(url_for('login'))

        user_id = user[0]

        # Check if the recipe is already in the user's favorites
        cursor.execute("SELECT * FROM favorite WHERE user_id = %s AND recipe_id = %s", (user_id, recipe_id))
        if cursor.fetchone():
            flash('Recipe is already in your favorites.', 'info')
            return redirect(url_for('favorite_list'))

        # Add the recipe to favorites
        cursor.execute("INSERT INTO favorite (user_id, recipe_id) VALUES (%s, %s)", (user_id, recipe_id))
        conn.commit()

        flash('Recipe added to favorites!', 'success')
        return redirect(url_for('favorite_list'))

    except Exception as e:
        app.logger.error(f"Error adding to favorites: {e}")
        flash("An error occurred while adding the recipe to your favorites.", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/remove_from_favorites/<int:recipe_id>', methods=['POST'])
def remove_from_favorites(recipe_id):
    """Remove a recipe from the user's favorites."""
    if 'username' not in session:
        flash('You must log in to remove from your favorites.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    conn = connect_db()

    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('favorite_list'))

    cursor = conn.cursor()

    try:
        # Fetch user ID
        cursor.execute("SELECT id FROM user WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", 'error')
            return redirect(url_for('login'))

        user_id = user[0]

        # Remove the recipe from favorites
        cursor.execute("DELETE FROM favorite WHERE user_id = %s AND recipe_id = %s", (user_id, recipe_id))
        conn.commit()

        flash('Recipe removed from favorites.', 'success')
        return redirect(url_for('favorite_list'))

    except Exception as e:
        app.logger.error(f"Error removing from favorites: {e}")
        flash("An error occurred while removing the recipe from your favorites.", 'error')
        return redirect(url_for('favorite_list'))

    finally:
        cursor.close()
        conn.close()

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)  # Remove user from the session
    flash('You have successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/admin_manage_recipe', methods=['GET', 'POST'])
def admin_manage_recipe():
    conn = connect_db()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor()

    try:
        if request.method == 'POST':
            recipe_id = request.form.get('recipe_id')
            action = request.form.get('action')

            if action == 'edit':
                return redirect(url_for('update_recipe', recipe_id=recipe_id))

            elif action == 'delete':
                try:
                    # Fetch the image URL to delete the associated image file
                    cursor.execute("SELECT image_url FROM recipe WHERE id = %s", (recipe_id,))
                    recipe = cursor.fetchone()
                    if recipe and recipe[0]:
                        image_path = os.path.join('static', recipe[0])
                        if os.path.exists(image_path):
                            os.remove(image_path)

                    # Delete the recipe from the database
                    cursor.execute("DELETE FROM recipe WHERE id = %s", (recipe_id,))
                    conn.commit()
                    flash('Recipe deleted successfully!', 'success')
                except Exception as e:
                    flash(f"Error deleting recipe: {e}", 'error')
        
        # Fetch all recipes to display
        cursor.execute("SELECT id, name, category, ingredient, instructions, image_url, time FROM recipe")
        recipes = cursor.fetchall()
        return render_template('admin_manage_recipe.html', recipes=recipes)

    except Exception as e:
        flash(f"An error occurred: {e}", 'error')
        return redirect(url_for('admin_dashboard'))

    finally:
        cursor.close()
        conn.close()


@app.route('/update_recipe/<int:recipe_id>', methods=['GET', 'POST'])
def update_recipe(recipe_id):
    conn = connect_db()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('admin_manage_recipe'))

    cursor = conn.cursor()

    try:
        if request.method == 'POST':
            # Retrieve form data
            name = request.form.get('name', '').strip()
            category = request.form.get('category', '').strip()
            ingredient = request.form.get('ingredient', '').strip()
            instructions = request.form.get('instructions', '').strip()
            time = request.form.get('time', '').strip()
            image_file = request.files.get('image')

            # Validate fields
            if not name or not category or not ingredient or not instructions or not time:
                flash('All fields are required.', 'error')
                return redirect(request.url)

            if not time.isdigit():
                flash('Cooking time must be a valid number.', 'error')
                return redirect(request.url)

            # Handle image upload
            image_path = request.form.get('existing_image')  # Default to existing image
            if image_file and image_file.filename:
                image_filename = secure_filename(image_file.filename)
                image_path = os.path.join('static', 'images', image_filename)
                # Ensure the directory exists
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image_file.save(image_path)

            # Update the database
            try:
                update_query = """
                    UPDATE recipe
                    SET name = %s, category = %s, ingredient = %s, instructions = %s, image_url = %s, time = %s
                    WHERE id = %s
                """
                cursor.execute(update_query, (name, category, ingredient, instructions, image_path, time, recipe_id))
                conn.commit()
                flash('Recipe updated successfully!', 'success')
                return redirect(url_for('admin_manage_recipe'))
            except Exception as e:
                flash(f"Error updating recipe: {e}", 'error')
                return redirect(url_for('admin_manage_recipe'))

        # GET request: Fetch the recipe details for editing
        cursor.execute("SELECT id, name, category, ingredient, instructions, image_url, time FROM recipe WHERE id = %s", (recipe_id,))
        recipe = cursor.fetchone()
        if recipe:
            return render_template('update_recipe.html', recipe=recipe)
        else:
            flash('Recipe not found.', 'error')
            return redirect(url_for('admin_manage_recipe'))

    except Exception as e:
        flash(f"An unexpected error occurred: {e}", 'error')
        return redirect(url_for('admin_manage_recipe'))

    finally:
        cursor.close()
        conn.close()

@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    conn = connect_db()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('admin_manage_recipe'))

    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM recipe WHERE id = %s", (recipe_id,))
        conn.commit()
        flash('Recipe deleted successfully!', 'success')
    except Exception as e:
        flash(f"Error deleting recipe: {e}", 'error')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_manage_recipe'))


@app.route('/chicken')
def chicken():
    if 'username' not in session:
        flash('You must log in to view recipes.', 'error')
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    conn = connect_db()
    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all chicken recipes
        query = "SELECT name, image_url, time FROM recipe WHERE category = 'Chicken'"
        cursor.execute(query)
        chicken_recipes = cursor.fetchall()

        return render_template('chicken.html', chicken_recipes=chicken_recipes)

    except Exception as e:
        flash(f"Error fetching chicken recipes: {e}", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/beef')
def beef():
    if 'username' not in session:
        flash('You must log in to view recipes.', 'error')
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    conn = connect_db()
    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all chicken recipes
        query = "SELECT name, image_url, time FROM recipe WHERE category = 'Beef'"
        cursor.execute(query)
        beef_recipes = cursor.fetchall()

        return render_template('beef.html', beef_recipes=beef_recipes)

    except Exception as e:
        flash(f"Error fetching beef recipes: {e}", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/pork')
def pork():
    if 'username' not in session:
        flash('You must log in to view recipes.', 'error')
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    conn = connect_db()
    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all chicken recipes
        query = "SELECT name, image_url, time FROM recipe WHERE category = 'Pork'"
        cursor.execute(query)
        pork_recipes = cursor.fetchall()

        return render_template('pork.html', pork_recipes=pork_recipes)

    except Exception as e:
        flash(f"Error fetching pork recipes: {e}", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/egg')
def egg():
    if 'username' not in session:
        flash('You must log in to view recipes.', 'error')
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    conn = connect_db()
    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all chicken recipes
        query = "SELECT name, image_url, time FROM recipe WHERE category = 'Egg'"
        cursor.execute(query)
        egg_recipes = cursor.fetchall()

        return render_template('egg.html', egg_recipes=egg_recipes)

    except Exception as e:
        flash(f"Error fetching egg recipes: {e}", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/soup')
def soup():
    if 'username' not in session:
        flash('You must log in to view recipes.', 'error')
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    conn = connect_db()
    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all chicken recipes
        query = "SELECT name, image_url, time FROM recipe WHERE category = 'Soup'"
        cursor.execute(query)
        soup_recipes = cursor.fetchall()

        return render_template('soup.html', soup_recipes=soup_recipes)

    except Exception as e:
        flash(f"Error fetching soup recipes: {e}", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()


@app.route('/bread')
def bread():
    if 'username' not in session:
        flash('You must log in to view recipes.', 'error')
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    conn = connect_db()
    if conn is None:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all chicken recipes
        query = "SELECT name, image_url, time FROM recipe WHERE category = 'Bread'"
        cursor.execute(query)
        bread_recipes = cursor.fetchall()

        return render_template('bread.html', bread_recipes=bread_recipes)

    except Exception as e:
        flash(f"Error fetching bread recipes: {e}", 'error')
        return redirect(url_for('main_dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/ingredient/<category>/<name>')
def ingredient(category, name):
    if 'username' not in session:
        flash('You must log in to view recipes.', 'error')
        return redirect(url_for('login'))

    conn = connect_db()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT name, image_url, ingredient, instructions 
            FROM recipe 
            WHERE category = %s AND name = %s
        """
        cursor.execute(query, (category, name))
        recipe = cursor.fetchone()

        if not recipe:
            flash("Recipe not found.", 'error')
            return redirect(url_for('main_dashboard'))

        recipe['ingredient'] = recipe['ingredient'].split(',') if recipe['ingredient'] else []
        recipe['instructions'] = recipe['instructions'].split('\n') if recipe['instructions'] else []

        return render_template('ingredient.html', recipe=recipe, category=category)
    finally:
        cursor.close()
        conn.close()




if __name__ == '__main__':
    app.run(debug=True)
