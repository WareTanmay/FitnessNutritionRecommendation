import random
import os
import re
from itertools import product

import MySQLdb.cursors
import pandas as pd
from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)
from flask_mysqldb import MySQL
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import train_test_split

app = Flask(__name__)
#app.secret_key = 'your_secret_key_here'  # Change this!

# -----------------------
# MySQL (phpMyAdmin) Configuration
# -----------------------
#app.config['MYSQL_HOST'] = 'localhost'
#app.config['MYSQL_USER'] = 'root'
#app.config['MYSQL_PASSWORD'] = '2004'
#app.config['MYSQL_DB'] = 'fitness'

# App secret key
#app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

# MySQL Configuration (from environment variables)
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 18729))
app.config['MYSQL_SSL_CA'] = os.environ.get('MYSQL_SSL_CA', 'ca.pem')
mysql = MySQL(app)

# -----------------------
# User Authentication Routes
# -----------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # For production, compare hashed passwords instead of plaintext!
        cursor.execute('SELECT * FROM accounts WHERE username = %s AND password = %s', (username, password))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            flash('Logged in successfully!')
            return redirect(url_for('index_old'))
        else:
            msg = 'Incorrect username/password!'
    return render_template('login.html', msg=msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = %s', (username,))
        account = cursor.fetchone()
        if account:
            msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers!'
        elif not username or not password or not email:
            msg = 'Please fill out the form!'
        else:
            cursor.execute('INSERT INTO accounts VALUES (NULL, %s, %s, %s)', (username, password, email))
            mysql.connection.commit()
            msg = 'You have successfully registered!'
    elif request.method == 'POST':  
        msg = 'Please fill out the form!'
    return render_template('register.html', msg=msg)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    flash('You have been logged out!')
    return redirect(url_for('login'))

@app.route('/index_old')
def index_old():
    return render_template('index_old.html')

# -----------------------
# Your Existing Machine Learning & Planner Code
# -----------------------

# Load datasets
exercise_df = pd.read_csv('new_cleaned_exercise_dataset.csv')
nutrition_df = pd.read_csv('neutritionData1.csv')

# Train a regression model to predict calorie intake
X_nutrition = nutrition_df[['Protein (g)', 'Carbs (g)', 'Fat (g)']]
y_nutrition = nutrition_df['Total Calories']
X_train, X_test, y_train, y_test = train_test_split(X_nutrition, y_nutrition, test_size=0.2, random_state=42)
rf_regressor = RandomForestRegressor(n_estimators=100, random_state=42)
rf_regressor.fit(X_train, y_train)

y_pred = rf_regressor.predict(X_test)
mape = mean_absolute_percentage_error(y_test, y_pred)
accuracy = 100 - (mape * 100)

# Activity level mapping
activity_level_mapping = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very active": 1.9
}

# Define muscles for the workout plan
muscle_groups = {
    'chest': ['chest'],
    'back': ['back'],
    'shoulder': ['shoulder'],
    'biceps': ['biceps'],
    'triceps': ['triceps'],
    'legs': ['legs'],
    'core': ['core']
}

# Workout plan logic for single or double muscle groups per day
def generate_workout_plan(focus, difficulty, num_weeks):
    workout_plan = []
    if focus == "single":
        # Single muscle focus: Assign one muscle per day
        weekly_schedule = [
            'chest', 'shoulder', 'biceps', 'triceps', 'back', 'legs', 'rest'
        ]
    else:
        # Double muscle focus: Assign two muscles per day
        weekly_schedule = [
            ('chest', 'shoulder'), ('biceps', 'triceps'), ('back', 'legs'), 
            ('shoulder', 'chest'), ('biceps', 'back'), ('legs', 'triceps'), ('rest', 'rest')
        ]

    for week in range(1, num_weeks + 1):
        for day in range(1, 8):
            daily_exercises = []
            if focus == "single":
                target_muscle = weekly_schedule[day - 1]
                if target_muscle != 'rest':
                    filtered_exercises = exercise_df[exercise_df['Targeted Muscle'].str.lower().isin(muscle_groups[target_muscle])]
                    if not filtered_exercises.empty:
                        daily_exercises = random.sample(list(filtered_exercises['Exercise Name']), min(3, len(filtered_exercises)))
                    else:
                        daily_exercises = ["No available exercises for this muscle group."]
            else:
                target_muscle_1, target_muscle_2 = weekly_schedule[day - 1]
                if target_muscle_1 != 'rest' and target_muscle_2 != 'rest':
                    filtered_exercises_1 = exercise_df[exercise_df['Targeted Muscle'].str.lower().isin(muscle_groups[target_muscle_1])]
                    filtered_exercises_2 = exercise_df[exercise_df['Targeted Muscle'].str.lower().isin(muscle_groups[target_muscle_2])]
                    if not filtered_exercises_1.empty and not filtered_exercises_2.empty:
                        daily_exercises_1 = random.sample(list(filtered_exercises_1['Exercise Name']), min(2, len(filtered_exercises_1)))
                        daily_exercises_2 = random.sample(list(filtered_exercises_2['Exercise Name']), min(2, len(filtered_exercises_2)))
                        daily_exercises = daily_exercises_1 + daily_exercises_2
                    else:
                        daily_exercises = ["No available exercises for these muscle groups."]
                else:
                    daily_exercises = ["Rest day."]
            
            workout_plan.append({
                'week': week,
                'day': day,
                'workout': [f"{exercise} - 3 sets x 8 reps" for exercise in daily_exercises]
            })
    return workout_plan

def generate_meal_plan(diet_type, daily_calories, num_weeks):
    meal_plan = []
    diet_type = diet_type.lower()
    meal_slots = ['breakfast', 'lunch', 'dinner', 'snack']
    target_per_meal = daily_calories / len(meal_slots)
    filtered_meals = nutrition_df[nutrition_df['Veg / Non-veg'].str.lower() == diet_type]

    # Fallback to entire dataset if no meals match requested diet_type
    if filtered_meals.empty:
        filtered_meals = nutrition_df.copy()

    # Precompute candidate meals for each time of day
    slot_candidates = {}
    for slot in meal_slots:
        slot_df = filtered_meals[filtered_meals['Time of Day'].str.lower() == slot].copy()
        if slot_df.empty:
            # Fallback to matching slot from the global dataset
            slot_df = nutrition_df[nutrition_df['Time of Day'].str.lower() == slot].copy()
        if slot_df.empty:
            # Absolute fallback: any meal
            slot_df = filtered_meals.copy()

        # Prioritize meals whose calories are closest to target_per_meal
        # Increase candidates to 10 to allow for more variety
        slot_df['calorie_diff'] = (slot_df['Total Calories'] - target_per_meal).abs()
        slot_df = slot_df.nsmallest(10, 'calorie_diff').drop(columns=['calorie_diff'])
        slot_candidates[slot] = slot_df.to_dict(orient='records')

    # Generate all combinations once
    candidate_lists = [slot_candidates[slot] for slot in meal_slots]
    all_combos = list(product(*candidate_lists))
    
    if not all_combos:
        # Handle case with no combos
        return [{'week': w, 'day': d, 'diet': ["No meals found"], 'macros': None, 'predicted_calories': 0, 'actual_calories': 0} 
                for w in range(1, num_weeks+1) for d in range(1, 8)]

    # Prepare features for batch prediction
    # Features: Total Protein, Total Carbs, Total Fat
    combo_features = []
    combo_details = []
    
    for combo in all_combos:
        p = sum(meal['Protein (g)'] for meal in combo)
        c = sum(meal['Carbs (g)'] for meal in combo)
        f = sum(meal['Fat (g)'] for meal in combo)
        cal = sum(meal['Total Calories'] for meal in combo)
        combo_features.append([p, c, f])
        combo_details.append({
            'combo': combo,
            'macros': {'protein': round(p, 1), 'carbs': round(c, 1), 'fats': round(f, 1)},
            'actual_calories': round(cal, 1)
        })

    # Batch predict
    predictions = rf_regressor.predict(combo_features)
    
    # Find best matches
    valid_options = []
    for i, pred in enumerate(predictions):
        diff = abs(pred - daily_calories)
        valid_options.append({
            **combo_details[i],
            'predicted_calories': round(pred, 1),
            'diff': diff
        })
    
    # Sort by difference and take top 50 for variety
    valid_options.sort(key=lambda x: x['diff'])
    top_options = valid_options[:50]

    for week in range(1, num_weeks + 1):
        for day in range(1, 8):
            # Randomly select one of the best options
            selection = random.choice(top_options)
            
            diet_entries = [
                f"{meal['Time of Day']}: {meal['Recipe Name']} - {meal['Total Calories']} kcal "
                f"(P {meal['Protein (g)']}g / C {meal['Carbs (g)']}g / F {meal['Fat (g)']}g)"
                for meal in selection['combo']
            ]

            meal_plan.append({
                'week': week,
                'day': day,
                'diet': diet_entries,
                'predicted_calories': selection['predicted_calories'],
                'actual_calories': selection['actual_calories'],
                'macros': selection['macros']
            })
    return meal_plan

# -----------------------
# Application Routes
# -----------------------

@app.route('/')
def index():
    # You can modify the index page to show different options based on whether the user is logged in.
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    # Require user to be logged in to access the predictor
    if 'loggedin' not in session:
        flash("Please login to use the predictor.")
        return redirect(url_for('login'))
    
    # Get form data
    name = request.form['name']
    height_cm = float(request.form['height'])
    weight_kg = float(request.form['weight'])
    goal = request.form['goal'].lower()
    activity_level_str = request.form['activity_level'].lower()
    focus = request.form['focus'].lower()  # Single or Double muscle focus
    difficulty = int(request.form['difficulty'])
    num_weeks = int(request.form['num_weeks'])
    diet_type = request.form['diet_type'].lower()
    age = int(request.form['age'])
    gender = request.form['gender'].lower()

    # Generate workout plan
    workout_plan = generate_workout_plan(focus, difficulty, num_weeks)
    
    # Activity level mapping
    activity_level = activity_level_mapping.get(activity_level_str, 1.2)
    
    # Calculate BMR using the Mifflin-St Jeor formula
    if gender == 'male':
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    elif gender == 'female':
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age  # default

    tdee = bmr * activity_level

    # Calorie intake adjustments based on goal
    if goal == "bulking":
        daily_calories = tdee * 1.2
    elif goal == "cutting":
        daily_calories = tdee * 0.8
    else:
        daily_calories = tdee

    # Macronutrient breakdown
    protein = round((daily_calories * 0.3) / 4, 1)
    carbs = round((daily_calories * 0.4) / 4, 1)
    fats = round((daily_calories * 0.3) / 9, 1)

    # Generate meal plan
    meal_plan = generate_meal_plan(diet_type, daily_calories, num_weeks)

    # Merge workout plan and meal plan
    full_plan = []
    for i in range(len(workout_plan)):
        full_plan.append({
            'week': workout_plan[i]['week'],
            'day': workout_plan[i]['day'],
            'workout': workout_plan[i]['workout'],
            'diet': meal_plan[i]['diet'],
            'predicted_calories': meal_plan[i].get('predicted_calories'),
            'actual_calories': meal_plan[i].get('actual_calories'),
            'macros': meal_plan[i].get('macros')
        })

    return render_template('result.html', name=name, daily_calories=round(daily_calories, 2), 
                           protein=protein, carbs=carbs, fats=fats, plan=full_plan)

if __name__ == '__main__':
    app.run(port=5001)
