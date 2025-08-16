import smtplib
from flask import Flask, request, jsonify
from js import ReminderExtractor
from supabase import create_client
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz


load_dotenv()






# Load variables from .env file

# Initialize Flask
app = Flask(__name__)
CORS(app)

api = os.environ["GROQ_API_KEY"]
# Initialize ReminderExtractor
extractor = ReminderExtractor(api_key=api)

# Initialize Supabase

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.route("/set-reminder", methods=["POST"])
def set_reminder():
    try:
        data = request.get_json()
        reminder_text = data.get("reminder_text")

        if not reminder_text:
            return jsonify({"error": "Missing reminder_text"}), 400

        current_time = datetime.now()
        result = extractor.extract(reminder_text, current_time)

        # Prepare data for Supabase
        reminder_data = {
            "hour": result["hour"],
            "min": result["minute"],  # Column is named 'min' in DB
            "message": result["reminder_message"]
        }

        # Insert into Supabase
        response = supabase.table("appointments").insert(reminder_data).execute()

        return jsonify({
            "status": "success",
            "data": reminder_data,
            "supabase_response": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Timezone (optional, set to your location)
IST = pytz.timezone('Asia/Kolkata')



def run_reminder(message):
    try:
        sender = "manitaverma8@gmail.com"
        reciever = "sarthak.molu08@gmail.com"
        message = message
        server = smtplib.SMTP("smtp.gmail.com" , 587)
        server.starttls()
        server.login(sender , "kcxpuypssxfwhlwv")
        server.sendmail(sender, reciever, message)
    except Exception as e:
        print(f"⚠️ Unexpected error during call: {e}")
        # Optional: log to DB




@app.route('/load_reminders', methods=['GET'])
def load_reminders():
    # Clear old jobs to avoid duplicate scheduling
    scheduler.remove_all_jobs()

    # Fetch from Supabase
    response = supabase.table("appointments").select("*").execute()
    appointments = response.data

    if not appointments:
        return jsonify({"status": "no reminders found"})

    now = datetime.now(IST)

    for appointment in appointments:
        reminder_id = appointment.get("id")  # assuming 'id' column exists in DB
        hour = appointment.get("hour")
        minute = appointment.get("min")
        message = appointment.get("message")

        reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if reminder_time <= now:
            if 0 <= (now - reminder_time).total_seconds() <= 60:
                print(f"⏰ Running immediately: {message}")
                run_reminder(message)
                # Delete from Supabase after execution
                supabase.table("appointments").delete().eq("id", reminder_id).execute()
                continue
            else:
                reminder_time += timedelta(days=1)

        def reminder_and_delete(msg, reminder_id):
            run_reminder(msg)
            supabase.table("appointments").delete().eq("id", reminder_id).execute()

        scheduler.add_job(reminder_and_delete, 'date', run_date=reminder_time, args=[message, reminder_id])
        print(f"✅ Scheduled: {message} at {reminder_time}")

    return jsonify({"status": "reminders loaded", "count": len(appointments)})



if __name__ == "__main__":
    app.run(debug=True)
