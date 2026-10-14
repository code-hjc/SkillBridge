from flask import Flask, render_template, request, session, redirect, flash
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)

# Secret key
app.secret_key = "skillbridge_secret_key"


# =========================
# MYSQL DATABASE
# =========================

db = mysql.connector.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", "SkillBridge@2006"),
    database=os.environ.get("DB_NAME", "skillbridge"),
    port=int(os.environ.get("DB_PORT", "3306"))
)

# =========================
# CAREER READINESS HELPER
# =========================

def calculate_career_readiness(user_id):

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT skill_level
        FROM user_skills
        WHERE user_id = %s
        """,
        (user_id,)
    )

    skill_levels = cursor.fetchall()

    cursor.execute(
        """
        SELECT goal_id
        FROM career_goals
        WHERE user_id = %s
        """,
        (user_id,)
    )

    has_goal = cursor.fetchone()

    cursor.close()

    level_points = {
        "Beginner": 40,
        "Intermediate": 70,
        "Advanced": 90
    }

    if skill_levels:

        total_points = sum(
            level_points.get(
                skill["skill_level"],
                40
            )
            for skill in skill_levels
        )

        career_readiness = round(
            total_points / len(skill_levels)
        )

    else:
        career_readiness = 0

    # Career goal bonus
    if has_goal:
        career_readiness += 10

    return min(career_readiness, 100)


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# SIGNUP
# =========================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:

            return render_template(
                "signup.html",
                error="Passwords do not match. Please try again."
            )

        cursor = db.cursor()

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()

            return render_template(
                "signup.html",
                error="Account already registered. Please login with your existing account."
            )

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users
            (full_name, email, password)
            VALUES (%s, %s, %s)
            """,
            (name, email, hashed_password)
        )

        db.commit()
        cursor.close()

        return redirect("/login")

    return render_template("signup.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["user_id"]
            session["user_name"] = user["full_name"]
            session["user_email"] = user["email"]

            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Invalid email or password. Please try again."
        )

    return render_template("login.html")


# =========================
# FORGOT PASSWORD
# =========================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"].strip()
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        # Password length check
        if len(new_password) < 8:
            return render_template(
                "forgot_password.html",
                error="Password must be at least 8 characters long."
            )

        # Password confirmation check
        if new_password != confirm_password:
            return render_template(
                "forgot_password.html",
                error="Passwords do not match. Please try again."
            )

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            cursor.close()

            return render_template(
                "forgot_password.html",
                error="No account found with this email address."
            )

        # Hash the new password
        hashed_password = generate_password_hash(new_password)

        cursor.execute(
            """
            UPDATE users
            SET password = %s
            WHERE user_id = %s
            """,
            (
                hashed_password,
                user["user_id"]
            )
        )

        db.commit()
        cursor.close()

        return redirect("/login")

    return render_template("forgot_password.html")


# =========================
# JOBS
# =========================

@app.route("/jobs")
def jobs():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            j.job_id,
            j.job_title,
            j.company_name,
            j.location,
            j.job_type,
            j.salary,
            j.description,
            j.application_link,
            s.skill_name
        FROM jobs j
        LEFT JOIN skills s
            ON j.required_skill_id = s.skill_id
        ORDER BY j.job_id
        """
    )

    jobs_list = cursor.fetchall()

    cursor.close()

    return render_template(
        "jobs.html",
        jobs=jobs_list
    )


# =========================
# COURSES
# =========================

@app.route("/courses")
def courses():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            c.course_id,
            c.course_name,
            c.description,
            c.duration,
            c.level,
            c.course_link,
            s.skill_name
        FROM courses c
        LEFT JOIN skills s
            ON c.skill_id = s.skill_id
        ORDER BY c.course_id
        """
    )

    courses_list = cursor.fetchall()

    cursor.close()

    return render_template(
        "courses.html",
        courses=courses_list
    )


# =========================
# MY SKILLS
# =========================

@app.route("/skills", methods=["GET", "POST"])
def skills():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    # ADD / UPDATE SKILL
    if request.method == "POST":

        skill_id = request.form["skill_id"]
        skill_level = request.form["skill_level"]
        user_id = session["user_id"]

        cursor.execute(
            """
            SELECT user_skill_id
            FROM user_skills
            WHERE user_id = %s
            AND skill_id = %s
            """,
            (user_id, skill_id)
        )

        existing_skill = cursor.fetchone()

        if existing_skill:

            cursor.execute(
                """
                UPDATE user_skills
                SET skill_level = %s
                WHERE user_skill_id = %s
                """,
                (
                    skill_level,
                    existing_skill["user_skill_id"]
                )
            )

        else:

            cursor.execute(
                """
                INSERT INTO user_skills
                (user_id, skill_id, skill_level)
                VALUES (%s, %s, %s)
                """,
                (
                    user_id,
                    skill_id,
                    skill_level
                )
            )

        db.commit()

        cursor.close()

        return redirect("/skills")

    # ALL SKILLS
    cursor.execute(
        """
        SELECT
            skill_id,
            skill_name
        FROM skills
        ORDER BY skill_name
        """
    )

    skills_list = cursor.fetchall()

    # USER SKILLS
    cursor.execute(
        """
        SELECT
            us.user_skill_id,
            s.skill_id,
            s.skill_name,
            s.description,
            us.skill_level
        FROM user_skills us
        JOIN skills s
            ON us.skill_id = s.skill_id
        WHERE us.user_id = %s
        ORDER BY s.skill_name
        """,
        (session["user_id"],)
    )

    user_skills = cursor.fetchall()

    cursor.close()

    return render_template(
        "skills.html",
        skills=skills_list,
        user_skills=user_skills
    )


# =========================
# CAREER GOAL
# =========================

@app.route("/career-goal", methods=["GET", "POST"])
def career_goal():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    user_id = session["user_id"]

    if request.method == "POST":

        goal_name = request.form["goal_name"].strip()

        if goal_name:

            cursor.execute(
                """
                SELECT goal_id
                FROM career_goals
                WHERE user_id = %s
                """,
                (user_id,)
            )

            existing_goal = cursor.fetchone()

            if existing_goal:

                cursor.execute(
                    """
                    UPDATE career_goals
                    SET goal_name = %s
                    WHERE user_id = %s
                    """,
                    (
                        goal_name,
                        user_id
                    )
                )

            else:

                cursor.execute(
                    """
                    INSERT INTO career_goals
                    (user_id, goal_name)
                    VALUES (%s, %s)
                    """,
                    (
                        user_id,
                        goal_name
                    )
                )

            db.commit()

    cursor.execute(
        """
        SELECT
            goal_id,
            goal_name
        FROM career_goals
        WHERE user_id = %s
        """,
        (user_id,)
    )

    goal = cursor.fetchone()

    cursor.close()

    return render_template(
        "career_goal.html",
        goal=goal
    )


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cursor = db.cursor()

    # SKILLS COUNT
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM user_skills
        WHERE user_id = %s
        """,
        (user_id,)
    )

    skills_count = cursor.fetchone()[0]

    # COURSES COUNT
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM courses
        """
    )

    courses_count = cursor.fetchone()[0]

    # JOBS COUNT
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        """
    )

    jobs_count = cursor.fetchone()[0]

    cursor.close()

    # CAREER READINESS
    career_readiness = calculate_career_readiness(user_id)

    # =========================
    # USER SKILLS
    # =========================

    skill_cursor = db.cursor(dictionary=True)

    skill_cursor.execute(
        """
        SELECT
            s.skill_name,
            us.skill_level
        FROM user_skills us
        JOIN skills s
            ON us.skill_id = s.skill_id
        WHERE us.user_id = %s
        ORDER BY s.skill_name
        """,
        (user_id,)
    )

    user_skill_data = skill_cursor.fetchall()

    skill_cursor.close()

    # =========================
    # RECOMMENDED COURSES
    # =========================

    course_cursor = db.cursor(dictionary=True)

    course_cursor.execute(
        """
        SELECT
            c.course_name,
            c.description,
            c.duration,
            c.level,
            c.course_link,
            s.skill_name
        FROM courses c
        JOIN user_skills us
            ON c.skill_id = us.skill_id
        JOIN skills s
            ON c.skill_id = s.skill_id
        WHERE us.user_id = %s
        ORDER BY c.course_id
        LIMIT 3
        """,
        (user_id,)
    )

    recommended_courses = course_cursor.fetchall()

    course_cursor.close()

    # =========================
    # CAREER GOAL
    # =========================

    goal_cursor = db.cursor(dictionary=True)

    goal_cursor.execute(
        """
        SELECT goal_name
        FROM career_goals
        WHERE user_id = %s
        """,
        (user_id,)
    )

    goal = goal_cursor.fetchone()

    goal_cursor.close()

    return render_template(
        "dashboard.html",
        user_name=session["user_name"],
        user_email=session["user_email"],
        skills_count=skills_count,
        courses_count=courses_count,
        jobs_count=jobs_count,
        career_readiness=career_readiness,
        user_skill_data=user_skill_data,
        recommended_courses=recommended_courses,
        goal=goal
    )


# =========================
# DELETE CAREER GOAL
# =========================

@app.route("/delete-career-goal", methods=["POST"])
def delete_career_goal():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM career_goals
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    db.commit()

    cursor.close()

    return redirect("/dashboard")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================
# APPLY FOR JOB
# =========================

@app.route("/apply/<int:job_id>", methods=["POST"])
def apply_job(job_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor()

    # CHECK DUPLICATE APPLICATION
    cursor.execute(
        """
        SELECT application_id
        FROM applications
        WHERE user_id = %s
        AND job_id = %s
        """,
        (
            session["user_id"],
            job_id
        )
    )

    existing_application = cursor.fetchone()

    if existing_application:

        cursor.close()

        flash(
            "You have already applied for this job.",
            "error"
        )

        return redirect("/jobs")

    # INSERT APPLICATION
    cursor.execute(
        """
        INSERT INTO applications
        (user_id, job_id)
        VALUES (%s, %s)
        """,
        (
            session["user_id"],
            job_id
        )
    )

    db.commit()

    cursor.close()

    return redirect("/applications")


# =========================
# REMOVE SKILL
# =========================

@app.route("/remove-skill/<int:skill_id>", methods=["POST"])
def remove_skill(skill_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM user_skills
        WHERE user_id = %s
        AND skill_id = %s
        """,
        (
            session["user_id"],
            skill_id
        )
    )

    db.commit()

    cursor.close()

    return redirect("/skills")


# =========================
# CANCEL APPLICATION
# =========================

@app.route(
    "/cancel-application/<int:application_id>",
    methods=["POST"]
)
def cancel_application(application_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM applications
        WHERE application_id = %s
        AND user_id = %s
        """,
        (
            application_id,
            session["user_id"]
        )
    )

    db.commit()

    cursor.close()

    return redirect("/applications")


# =========================
# APPLICATIONS
# =========================

@app.route("/applications")
def applications():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            a.application_id,
            a.application_date,
            a.status,
            j.job_title,
            j.company_name,
            j.location,
            j.job_type,
            j.salary
        FROM applications a
        JOIN jobs j
            ON a.job_id = j.job_id
        WHERE a.user_id = %s
        ORDER BY a.application_date DESC
        """,
        (session["user_id"],)
    )

    applications_list = cursor.fetchall()

    cursor.close()

    return render_template(
        "applications.html",
        applications=applications_list
    )


# =========================
# PROFILE
# =========================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            user_id,
            full_name,
            email,
            college,
            course,
            created_at
        FROM users
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    user = cursor.fetchone()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM user_skills
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    skills_count = cursor.fetchone()["COUNT(*)"]

    cursor.close()

    # Same readiness calculation used everywhere
    career_readiness = calculate_career_readiness(
        session["user_id"]
    )

    return render_template(
        "profile.html",
        user=user,
        skills_count=skills_count,
        career_readiness=career_readiness
    )


# =========================
# EDIT PROFILE
# =========================

@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():

    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        full_name = request.form["full_name"]
        college = request.form["college"]
        course = request.form["course"]

        cursor.execute(
            """
            UPDATE users
            SET
                full_name = %s,
                college = %s,
                course = %s
            WHERE user_id = %s
            """,
            (
                full_name,
                college,
                course,
                session["user_id"]
            )
        )

        db.commit()

        session["user_name"] = full_name

        cursor.close()

        return redirect("/profile")

    cursor.execute(
        """
        SELECT
            full_name,
            email,
            college,
            course
        FROM users
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    user = cursor.fetchone()

    cursor.close()

    return render_template(
        "edit_profile.html",
        user=user
    )


# =========================
# PROGRESS
# =========================

@app.route("/progress")
def progress():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cursor = db.cursor(dictionary=True)

    # USER SKILLS
    cursor.execute(
        """
        SELECT
            s.skill_name,
            us.skill_level
        FROM user_skills us
        JOIN skills s
            ON us.skill_id = s.skill_id
        WHERE us.user_id = %s
        ORDER BY s.skill_name
        """,
        (user_id,)
    )

    skills = cursor.fetchall()

    # CAREER GOAL
    cursor.execute(
        """
        SELECT
            goal_name
        FROM career_goals
        WHERE user_id = %s
        """,
        (user_id,)
    )

    goal = cursor.fetchone()

    cursor.close()

    skills_count = len(skills)

    # Same readiness calculation as Dashboard/Profile
    career_readiness = calculate_career_readiness(
        user_id
    )

    return render_template(
        "progress.html",
        skills=skills,
        skills_count=skills_count,
        career_readiness=career_readiness,
        goal=goal
    )


# =========================
# RUN FLASK
# =========================

if __name__ == "__main__":
    app.run(debug=True)