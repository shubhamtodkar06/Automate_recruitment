from typing import Literal, Tuple, Dict, Optional
import time
import smtplib
import requests
import PyPDF2
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import streamlit as st
import json
import os
import pytz
import pandas as pd
import matplotlib.pyplot as plt
from phi.tools.zoom import ZoomTool
from phi.utils.log import logger
from streamlit_pdf_viewer import pdf_viewer


def display_analytics():
    # Load data from analytics.json
    try:
        with open("analytics.json", "r") as file:
            analytics_data = json.load(file)
    except FileNotFoundError:
        st.error("The file 'analytics.json' was not found.")
        return
    except json.JSONDecodeError:
        st.error("Error decoding JSON data. Please check the file format.")
        return

    # Extract role-based data
    role_data = analytics_data.get("roles", {})
    
    if not role_data:  # Check if role_data is empty
        st.warning("No role data available.")
        return
    
    role_df = pd.DataFrame(role_data).T  # Transpose to make roles rows instead of columns
    role_df.reset_index(inplace=True)
    role_df.rename(columns={"index": "Role"}, inplace=True)

    # Display role-based table with custom styling
    st.subheader("Role-Based Analytics")
    st.markdown("<style>table {background-color: #f0f8ff;}</style>", unsafe_allow_html=True)
    st.table(role_df.style.set_table_styles([ 
        {'selector': 'thead th', 'props': [('background-color', '#4CAF50'), ('color', 'white')]}, 
        {'selector': 'tbody td', 'props': [('background-color', '#f9f9f9'), ('color', 'black')]}, 
    ]))

    # Plot role-based bar graph
    st.subheader("Role-Based Bar Graph")
    fig, ax = plt.subplots(figsize=(10, 6))
    role_df.set_index("Role")[["total_applicants", "selected_for_test", "passed", "failed"]].plot(
        kind="bar", ax=ax, color=["#ff9999", "#66b3ff", "#99ff99", "#ffcc99"]
    )
    plt.title("Applicants Breakdown by Role", fontsize=14)
    plt.xlabel("Roles", fontsize=12)
    plt.ylabel("Number of Applicants", fontsize=12)
    plt.xticks(rotation=45)
    plt.legend(title="Metrics")
    st.pyplot(fig)

    # Pie chart for applicant distribution
    st.subheader("Applicant Distribution by Role (Pie Chart)")
    role_applicants = role_df[["Role", "total_applicants"]].set_index("Role")

    # Handle NaN values in the total_applicants column
    role_applicants["total_applicants"] = role_applicants["total_applicants"].fillna(0)

    # If the total_applicants column is empty or all zeros, show a warning
    if role_applicants["total_applicants"].sum() == 0:
        st.warning("No applicants data available for pie chart.")
    else:
        fig, ax = plt.subplots(figsize=(8, 8))
        role_applicants.plot.pie(y="total_applicants", ax=ax, autopct='%1.1f%%', legend=False)
        plt.title("Total Applicants by Role", fontsize=14)
        st.pyplot(fig)

    # Extract interview data
    interviews_data = analytics_data.get("interviews", [])
    if interviews_data:
        interview_df = pd.DataFrame(interviews_data)

        # Display interview table with custom styling
        st.subheader("Scheduled Interviews")
        st.markdown("<style>table {background-color: #fff0f5;}</style>", unsafe_allow_html=True)
        st.table(interview_df.style.set_table_styles([ 
            {'selector': 'thead th', 'props': [('background-color', '#ff6347'), ('color', 'white')]}, 
            {'selector': 'tbody td', 'props': [('background-color', '#f0e68c'), ('color', 'black')]}, 
        ]))

        # Plot interview count by role
        st.subheader("Interviews Per Role")
        role_counts = interview_df["role"].value_counts()
        fig, ax = plt.subplots(figsize=(8, 5))
        role_counts.plot(kind="bar", color="skyblue", ax=ax)
        plt.title("Number of Interviews by Role", fontsize=14)
        plt.xlabel("Role", fontsize=12)
        plt.ylabel("Number of Interviews", fontsize=12)
        plt.xticks(rotation=45)
        st.pyplot(fig)

        # Pie chart for interview distribution by role
        st.subheader("Interview Distribution by Role (Pie Chart)")
        interview_counts = interview_df["role"].value_counts()
        fig, ax = plt.subplots(figsize=(8, 8))
        interview_counts.plot.pie(autopct='%1.1f%%', ax=ax, legend=False)
        plt.title("Interviews by Role", fontsize=14)
        st.pyplot(fig)
    else:
        st.warning("No interviews data available.")

class CustomZoomTool(ZoomTool):
    def __init__(self, *, account_id: Optional[str] = None, client_id: Optional[str] = None, client_secret: Optional[str] = None, name: str = "zoom_tool"):
        super().__init__(account_id=account_id, client_id=client_id, client_secret=client_secret, name=name)
        self.token_url = "https://zoom.us/oauth/token"
        self.access_token = None
        self.token_expires_at = 0

    def get_access_token(self) -> str:
        if self.access_token and time.time() < self.token_expires_at:
            return str(self.access_token)
            
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "account_credentials", "account_id": self.account_id}

        try:
            response = requests.post(self.token_url, headers=headers, data=data, auth=(self.client_id, self.client_secret))
            response.raise_for_status()

            token_info = response.json()
            self.access_token = token_info["access_token"]
            expires_in = token_info["expires_in"]
            self.token_expires_at = time.time() + expires_in - 60

            self._set_parent_token(str(self.access_token))
            return str(self.access_token)

        except requests.RequestException as e:
            logger.error(f"Error fetching access token: {e}")
            return ""

    def _set_parent_token(self, token: str) -> None:
        """Helper method to set the token in the parent ZoomTool class"""
        if token:
            self._ZoomTool__access_token = token


# Role requirements as a constant dictionary
FILE_PATH = "roles.json"

# Default roles, which will be added to the file only if it is empty
ROLE_REQUIREMENTS = {
    "ai_ml_engineer": """
        Required Skills:
        - Python, PyTorch/TensorFlow
        - Machine Learning algorithms and frameworks
        - Deep Learning and Neural Networks
        - Data preprocessing and analysis
        - MLOps and model deployment
        - RAG, LLM, Finetuning and Prompt Engineering
    """,
    "frontend_engineer": """
        Required Skills:
        - React/Vue.js/Angular
        - HTML5, CSS3, JavaScript/TypeScript
        - Responsive design
        - State management
        - Frontend testing
    """,
    "backend_engineer": """
        Required Skills:
        - Python/Java/Node.js
        - REST APIs
        - Database design and management
        - System architecture
        - Cloud services (AWS/GCP/Azure)
        - Kubernetes, Docker, CI/CD
    """
}

def load_roles():
    """Load roles from the file, or return empty dict if the file doesn't exist or is empty."""
    try:
        with open(FILE_PATH, "r") as file:
            roles = json.load(file)
            if not roles:  # If file is empty, return an empty dict
                return {}
            return roles
    except FileNotFoundError:
        return {}

def save_roles(roles):
    """Save roles to the file."""
    with open(FILE_PATH, "w") as file:
        json.dump(roles, file, indent=4)

def load_mcqs(role_choice=""):
    """Load MCQs for the selected role or all roles from the JSON file."""
    try:
        with open("mcqs.json", "r") as file:
            mcqs_data = json.load(file)
            if role_choice:
                return mcqs_data.get(role_choice, [])  # Return MCQs for specific role
            return mcqs_data if isinstance(mcqs_data, dict) else {}  # Return all roles as a dictionary
    except FileNotFoundError:
        return {}  # Return empty dictionary if file is not found


def load_all_mcqs_roles():
    """Load all roles from the MCQs file."""
    try:
        with open("mcqs.json", "r") as file:
            mcqs_data = json.load(file)
            return list(mcqs_data.keys())  # Get all role names from MCQs
    except FileNotFoundError:
        return []
def save_mcqs(role_choice, role_mcqs):
    """Save MCQs for the selected role to the JSON file."""
    try:
        with open("mcqs.json", "r") as file:
            mcqs_data = json.load(file)
    except FileNotFoundError:
        mcqs_data = {}

    mcqs_data[role_choice] = role_mcqs

    with open("mcqs.json", "w") as file:
        json.dump(mcqs_data, file, indent=4)

def manage_roles():
    """Manage roles by allowing add, edit, or delete functionality."""
    roles = load_roles()

    if not roles:
        roles = ROLE_REQUIREMENTS.copy()
        save_roles(roles)

    if "custom_roles" not in st.session_state:
        st.session_state["custom_roles"] = roles

    st.sidebar.subheader("Modify or Add Role Criteria")

    role_choice = st.selectbox(
        "Select a role to modify or add:",
        list(st.session_state["custom_roles"].keys()) + ["Add New Role"]
    )

    if role_choice == "Add New Role":
        # Get existing roles from mcqs.json to display as suggestions
        existing_roles_in_mcqs = load_mcqs()  # Now it returns a dictionary
        existing_roles_in_mcqs_keys = list(existing_roles_in_mcqs.keys())  # Get all keys (role names)

        # Get the roles already present in roles.json
        existing_roles_in_json = list(st.session_state["custom_roles"].keys())

        # Exclude roles already in roles.json from suggestions
        suggested_roles = [role for role in existing_roles_in_mcqs_keys if role not in existing_roles_in_json]

        new_role = st.text_input("Enter the name of the new role:")

        # Show a dropdown of available roles from mcqs.json as suggestions
        if suggested_roles:
            st.write("Following Roles Already have MCQs(type similar spelling to access those):")
            st.write(", ".join(suggested_roles))

        st.write("If your role is not listed, you can type a new role name.")

        if new_role:
            # Check if the role already exists in roles.json
            if new_role in existing_roles_in_json:
                st.warning(f"Role '{new_role}' already exists in the roles file. Please choose another name or modify the existing role.")
                new_criteria = st.text_area("Enter the criteria for the new role:")
                if st.button("Add Role"):
                    st.session_state["custom_roles"][new_role] = new_criteria
                    save_roles(st.session_state["custom_roles"])  # Save the new role immediately
                    st.success(f"New role '{new_role}' added successfully.")
                    st.rerun()  # Rerun to reflect changes immediately
            elif new_role in existing_roles_in_mcqs_keys:
                st.warning(f"Role '{new_role}' already exists in the MCQs file. Using the existing MCQs for this role.")
                new_criteria = st.text_area("Enter the criteria for the new role:", value="Enter Criteria for role", height=150)
                if st.button("Add Role"):
                    st.session_state["custom_roles"][new_role] = new_criteria
                    save_roles(st.session_state["custom_roles"])  # Save the new role immediately
                    st.success(f"New role '{new_role}' added successfully with existing MCQs.")
                    
            else:
                new_criteria = st.text_area("Enter the criteria for the new role:")
                if st.button("Add Role"):
                    if new_role.strip() == "":
                        st.error("Role name cannot be empty.")
                    elif not new_criteria.strip():
                        st.error("Please provide criteria for the new role.")
                    else:
                        st.session_state["custom_roles"][new_role] = new_criteria
                        save_roles(st.session_state["custom_roles"])  # Save the new role immediately
                        st.success(f"New role '{new_role}' added successfully.")
                        st.rerun()  # Rerun to reflect changes immediately
    else:
        st.markdown(f"### Current Criteria for {role_choice}:")
        st.text_area("", value=st.session_state["custom_roles"][role_choice], height=150, disabled=True)

        new_criteria = st.text_area(
            f"Modify the criteria for {role_choice}:",
            value=st.session_state["custom_roles"][role_choice]
        )
        
        if st.button("Save Changes"):
            if new_criteria.strip() == "":
                st.error("Criteria cannot be empty.")
            else:
                st.session_state["custom_roles"][role_choice] = new_criteria
                save_roles(st.session_state["custom_roles"])  # Save the change immediately
                st.success(f"Criteria for '{role_choice}' updated successfully.")
                st.rerun()  # Rerun to reflect changes immediately

        if st.button("Delete Role"):
            del st.session_state["custom_roles"][role_choice]
            save_roles(st.session_state["custom_roles"])  # Save after deletion
            st.success(f"Role '{role_choice}' deleted successfully.")
            st.rerun()  # Rerun to reflect changes immediately
            # Optionally remove MCQs if needed:
            st.warning(f"Role '{role_choice}' is deleted but its MCQs are kept in the system.")
            
            st.rerun()

        if role_choice != "Add New Role":
            edit_mcq_questions(role_choice)
            add_mcq_question(role_choice)

    if not st.session_state["custom_roles"]:
        st.session_state["custom_roles"] = ROLE_REQUIREMENTS.copy()
        save_roles(st.session_state["custom_roles"])

    return st.session_state["custom_roles"]

def edit_mcq_questions(role_choice):
    """Edit MCQs for the selected role."""
    role_mcqs = load_mcqs(role_choice)
    
    # Display the existing MCQs
    st.subheader(f"Existing MCQs for {role_choice}")
    
    if not role_mcqs:
        st.write("No questions found for this role.")
    
    for idx, question in enumerate(role_mcqs):
        st.markdown(f"### Question {idx + 1}")
        st.write(f"**Q:** {question['question']}")
        st.write(f"**Options:** {', '.join(question['options'])}")
        
        # Ensure the 'answer' key exists, if not, assign a default value
        answer = question.get('answer', 'No answer set')
        st.write(f"**Answer:** {answer}")
        
        # Option to edit the question
        with st.expander(f"Edit Question {idx + 1}"):

            new_question = st.text_input(f"Edit Question {idx + 1}: ", value=question['question'], key=f"question_{idx}")
            new_options = [st.text_input(f"Option {i + 1}: ", value=opt, key=f"option_{idx}_{i}") for i, opt in enumerate(question['options'])]
            new_answer = st.selectbox(f"Select Correct Answer for Question {idx + 1}", new_options, key=f"answer_{idx}")
            
            if st.button(f"Save Changes to Question {idx + 1}", key=f"save_{idx}"):
                if new_question.strip() == "" or not new_options or new_answer.strip() == "":
                    st.error("Please fill in all fields correctly.")
                else:
                    # Update the question with new data
                    role_mcqs[idx] = {"question": new_question, "options": new_options, "answer": new_answer}
                    save_mcqs(role_choice, role_mcqs)  # Save changes to file
                    st.success(f"Question {idx + 1} updated successfully.")
                    st.rerun()  # Rerun to reflect changes immediately
        
            # Button to delete the specific MCQ
            if st.button(f"Delete Question {idx + 1}", key=f"delete_{idx}"):
                role_mcqs.pop(idx)  # Remove the MCQ at the specified index
                save_mcqs(role_choice, role_mcqs)  # Save the updated list to file
                st.success(f"Question {idx + 1} deleted successfully.")
                st.rerun()  # Rerun to reflect changes immediately

def add_mcq_question(role_choice):
    """Add a new MCQ question for the selected role."""
    st.sidebar.subheader(f"Add New MCQ for {role_choice}")
    
    # Ensure that all four options are filled before proceeding
    new_question = st.text_input("Enter the new question:", key=f"new_question_{role_choice}")
    
    # MCQ options
    option_1 = st.text_input("Option 1:", key=f"option_1_{role_choice}")
    option_2 = st.text_input("Option 2:", key=f"option_2_{role_choice}")
    option_3 = st.text_input("Option 3:", key=f"option_3_{role_choice}")
    option_4 = st.text_input("Option 4:", key=f"option_4_{role_choice}")

    # Correct option
    correct_option = st.selectbox(
        "Select the correct option:",
        ["Option 1", "Option 2", "Option 3", "Option 4"],
        key=f"correct_option_{role_choice}"
    )

    # Validate that all fields are filled
    if st.button("Add MCQ"):
        if not new_question or not option_1 or not option_2 or not option_3 or not option_4:
            st.error("Please fill in all fields before adding the MCQ.")
        else:
            # Create the MCQ question object
            mcq_question = {
                "question": new_question,
                "options": [option_1, option_2, option_3, option_4],
                "answer": correct_option  # Fix the key from "correct_option" to "answer"
            }

            # Load existing MCQs for the role
            role_mcqs = load_mcqs(role_choice)
            
            # Add the new question to the list of MCQs for the role
            role_mcqs.append(mcq_question)

            # Save the updated MCQs back to the file
            save_mcqs(role_choice, role_mcqs)
            st.success(f"MCQ added for role '{role_choice}' successfully!")
            st.rerun()  # Rerun to reflect changes immediately

def schedule_meeting():
    """
    Allows the user to input a date and time for scheduling a meeting.
    Stores the data in session_state for later use.
    """
    st.sidebar.subheader("Schedule Meeting")

    # Date and Time Inputs
    meeting_date = st.date_input("Select Meeting Date:")
    meeting_time = st.time_input("Select Meeting Time:")

    # Combine date and time into a datetime object
    if meeting_date and meeting_time:
        scheduled_datetime = datetime.combine(meeting_date, meeting_time)
        st.session_state["scheduled_datetime"] = scheduled_datetime
        st.success(f"Meeting scheduled for: {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

    # Display scheduled date and time if already set
    if "scheduled_datetime" in st.session_state:
        st.sidebar.info(
            f"Scheduled Meeting:\n{st.session_state['scheduled_datetime'].strftime('%Y-%m-%d %H:%M:%S')}"
        )




def init_session_state() -> None:
    """Initialize only necessary session state variables."""
    defaults = {
        'candidate_email': "", 'openai_api_key': "", 'recruiter_email': "" ,'resume_text': "", 'analysis_complete': False,
        'is_selected': False, 'zoom_account_id': "", 'zoom_client_id': "", 'zoom_client_secret': "",
        'email_sender': "", 'email_passkey': "", 'company_name': "", 'current_pdf': None,
        'time_change_requested': False, 'scheduled_datetime': None, 'proceed_app' : False, 'test_conducted' : False,
        'check_it' : False, 'no_button' : False, 'time_and_date' : False, 'check_again' : False, 'fragment' : False, 'go_ahead' : False, 'session_to_proceed' : False,
        'show_analytics' : False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def extract_text_from_pdf(pdf_file) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting PDF text: {str(e)}")
        return ""


def analyze_resume(
    resume_text: str,
    role
) -> Tuple[bool, str]:
    try:
        # Manual response
        response = {
            "selected": True,
            "feedback": "The candidate meets over 70% of the required skills for the AI/ML Engineer role...",
            "matching_skills": ["Python", "Machine Learning", "Deep Learning", "Flask Framework", "DBMS", "C++"],
            "missing_skills": ["TensorFlow", "PyTorch", "Natural Language Processing", "Cloud Computing", "DevOps"],
            "experience_level": "junior"
        }

        # Directly return the values as a tuple
        return response["selected"], response["feedback"]

    except Exception as e:
        # Handle unexpected exceptions gracefully
        return False, f"Error analyzing resume: {str(e)}"


def send_selection_email(sender_email, sender_password, receiver_email, role, company) -> None:
    """Send an email with the given subject and body."""
    
    # Constructing the subject and body of the email
    subject = f"Congratulations! You have been selected for the {role} role"
    
    body = f"""
    Dear Candidate,
    
    Congratulations! We are pleased to inform you that you have been selected for the role of {role} at {company}.
    
    We believe you will be a great addition to the team, and we look forward to seeing the skills and expertise you will bring to this position.
    
    Please prepare yourself by reviewing relevant skills for the {role} role. You will be contacted shortly with further instructions regarding your start date and other preparations.
    
    Additionally, we will schedule a Zoom meeting soon to discuss the next steps and answer any questions you may have.
    
    Best regards,
    {company}
    """

    # Creating MIMEText object for email
    msg = MIMEText(body, 'plain', 'utf-8')
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    # Sending the email through Gmail's SMTP server
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()  # Start TLS encryption
        server.login(sender_email, sender_password)  # Login with the sender's credentials
        server.sendmail(sender_email, receiver_email, msg.as_string())  # Send the email


def send_rejection_email(sender_email, sender_password, receiver_email, role, company) -> None:
    """Send an email with the given subject and body."""
    
    # Constructing the subject and body of the rejection email
    subject = f"Regarding your application for the {role} role"
    
    body = f"""
    Dear Candidate,
    
    Thank you for your interest in the {role} role at {company}. Unfortunately, we regret to inform you that we will not be proceeding with your application at this time.
    
    While we were impressed with your qualifications, we have decided to move forward with other candidates who more closely match the requirements for this role.
    
    We encourage you to continue preparing and working hard to improve your skills. Please don't be discouraged—your next opportunity may be just around the corner. We welcome you to apply again for future positions with us.

    We wish you all the best in your career journey.
    
    Best regards,
    {company}
    """

    # Creating MIMEText object for email
    msg = MIMEText(body, 'plain', 'utf-8')
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    # Sending the email through Gmail's SMTP server
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()  # Start TLS encryption
        server.login(sender_email, sender_password)  # Login with the sender's credentials
        server.sendmail(sender_email, receiver_email, msg.as_string())  # Send the email
 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def schedule_interview(
    zoom_acc_id, zoom_client_id, zoom_secret, sender_email, 
    sender_password, receiver_email, recruiter_email, role: str, company: str, local_timezone: str
) -> None:
    try:
        # Ensure the date and time for scheduling are set
        if "scheduled_datetime" not in st.session_state:
            st.error("Please schedule a date and time for the interview first!")
            return
        
        # Step 1: Show the allocated interview time
        st.subheader("Interview Date & Time Allocation")
        
        # Check if the interview time has already been scheduled by the recruiter
        if 'scheduled_datetime' not in st.session_state:
            st.error("No interview time allocated by the recruiter yet.")
            return

        # Show the allocated interview date and time
        scheduled_datetime = st.session_state['scheduled_datetime']
        st.write(f"Your interview is scheduled for {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')} ({local_timezone})")

        # Convert the scheduled datetime to UTC for Zoom API
        local_tz = pytz.timezone(local_timezone)
        local_dt = local_tz.localize(scheduled_datetime, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        meeting_time_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # ISO 8601 format

        # Step 2: Get Zoom OAuth token
        zoom_token_url = "https://zoom.us/oauth/token"
        zoom_payload = {
            'grant_type': 'account_credentials',
            'account_id': zoom_acc_id
        }
        auth = (zoom_client_id, zoom_secret)

        token_response = requests.post(zoom_token_url, data=zoom_payload, auth=auth)
        token_response.raise_for_status()
        access_token = token_response.json().get('access_token')
        if not access_token:
            raise ValueError("Failed to fetch Zoom access token.")

        # Step 3: Schedule a Zoom meeting
        zoom_meeting_url = "https://api.zoom.us/v2/users/me/meetings"
        meeting_details = {
            "topic": f"Interview for {role}",
            "type": 2,  # Scheduled meeting
            "start_time": meeting_time_iso,
            "duration": 60,  # Meeting duration in minutes
            "timezone": "UTC",
            "settings": {
                "join_before_host": True,
                "waiting_room": False
            }
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        meeting_response = requests.post(zoom_meeting_url, json=meeting_details, headers=headers)
        meeting_response.raise_for_status()
        meeting_data = meeting_response.json()
        meeting_link = meeting_data.get('join_url')

        if not meeting_link:
            raise ValueError("Failed to schedule Zoom meeting.")

        # Step 4: Send email with meeting details
        subject = f"Interview Scheduled for {role} at {company}"
        body = f"""
        Dear Candidate,

        We are pleased to inform you that your interview for the {role} role at {company} has been scheduled.

        Meeting Details:
        - Link: {meeting_link}
        - Date: {scheduled_datetime.strftime('%Y-%m-%d')}
        - Time: {scheduled_datetime.strftime('%H:%M:%S')} ({local_timezone})

        Instructions:
        - Please ensure that you join the interview on time.
        - Test your camera and microphone in advance to ensure they are working correctly.
        - Use a quiet environment to avoid distractions during the interview.
        - Dress appropriately as you would for an in-person interview.
        - Ensure your internet connection is stable for a smooth interview experience.

        We look forward to meeting with you and discussing your qualifications for the {role} role.

        Best regards,
        {company} Hiring Team
        """

        # Properly format multiple recipients
        recipients = [receiver_email, recruiter_email]
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = ", ".join(recipients)  # Correctly format the To field
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)

        # Step 5: Update analytics.json with interview details
        analytics_file = "analytics.json"
        try:
            with open(analytics_file, "r") as file:
                analytics_data = json.load(file)
        except FileNotFoundError:
            analytics_data = {"roles": {}, "interviews": []}
        except json.JSONDecodeError:
            analytics_data = {"roles": {}, "interviews": []}

        # Add the interview details to the analytics data
        interview_details = {
            "email": receiver_email,
            "role": role,
            "time": scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            "link": meeting_link
        }
        analytics_data["interviews"].append(interview_details)

        # Save the updated analytics data
        with open(analytics_file, "w") as file:
            json.dump(analytics_data, file, indent=4)

        st.success("Interview scheduled successfully!")

    except Exception as e:
        logger.error(f"Error scheduling interview: {str(e)}")
        st.error("Unable to schedule interview. Please try again.")


def ask_for_time_change():
    """Asks the candidate if they want to change the interview time."""

    if "time_change_requested" not in st.session_state:
        st.session_state.time_change_requested = False

    current_time = st.session_state.get("scheduled_datetime", None)
    if not current_time:
        st.warning("No interview time assigned by the recruiter yet.")
        return

    st.write(f"Current interview time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Use a key for the radio button to maintain state across reruns
    change_time = st.radio("Would you like to change the interview time?", ["No", "Yes"], index=1, key="change_time_radio")
    print(change_time)
    
    if change_time == "Yes":
        st.session_state.time_change_requested = True  # set to true when user click yes
       

    elif change_time == "No":
        st.session_state.time_change_requested = False  # set to false when user click No
        st.write("You have opted to keep the original scheduled time.")

    return st.session_state.time_change_requested  # return the value to know whether to proceed with scheduling or not

def update_meeting_schedule():
    """
    Updates the meeting schedule by allowing the user to select from predefined dates and times.
    Updates st.session_state["scheduled_datetime"] accordingly.
    """
    st.sidebar.subheader("Update Meeting Schedule")

    # Load predefined available times from the JSON file
    with open(
        r"C:\Users\Admin\python_project\awesome-llm-apps\ai_agent_tutorials\ai_recruitment_agent_team\predefined_times.json",
        "r",
    ) as file:
        predefined_data = json.load(file)

    available_times = predefined_data.get("available_times", [])
    available_times_formatted = [datetime.strptime(t, "%Y-%m-%d %H:%M:%S") for t in available_times]

    # Display available times in a dropdown
    selected_time = st.selectbox(
        "Select a new meeting date and time:",
        options=available_times_formatted,
        format_func=lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
    )

    # Update session state if a selection is made
    if selected_time:
        if "scheduled_datetime" not in st.session_state or st.session_state["scheduled_datetime"] != selected_time:
            st.session_state["scheduled_datetime"] = selected_time
            st.success(f"Meeting updated to: {selected_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("No changes made to the meeting schedule.")

    # Display the updated date and time
    if "scheduled_datetime" in st.session_state:
        st.sidebar.info(
            f"Updated Meeting:\n"
            f"{st.session_state['scheduled_datetime'].strftime('%Y-%m-%d %H:%M:%S')}"
        )

def conduct_test_and_evaluate(role_choice):
    """Conducts the assessment test for the candidate and returns True if passed, False otherwise."""
    # Load MCQs for the selected role
    role_mcqs = load_mcqs(role_choice)
    if not role_mcqs:
        st.error("No MCQs available for this role.")
        return True

    # Initialize session state variables for the test
    test_state_key = f"{role_choice}_test_state"
    if test_state_key not in st.session_state:
        st.session_state[test_state_key] = {
            "progress": 0,
            "answers": [],
            "completed": False
        }

    test_state = st.session_state[test_state_key]
    progress = test_state["progress"]

    if not test_state["completed"]:
        # Get the current question
        current_question = role_mcqs[progress]

        # Display the question
        st.write(f"Question {progress + 1}: {current_question['question']}")
        selected_option = st.radio(
            label="Choose your answer:",
            options=current_question['options'],
            key=f"{role_choice}_test_question_{progress}"  # Unique key for each question
        )

        # Button to submit the current answer
        if st.button("Submit Answer", key=f"{role_choice}_submit_button_{progress}"):
            if not selected_option:
                st.warning("Please select an answer before proceeding.")
            else:
                # Record the selected answer
                test_state["answers"].append(selected_option)

                # Move to the next question or complete the test
                if progress + 1 < len(role_mcqs):
                    test_state["progress"] += 1
                    st.rerun()
                else:
                    # Test completed
                    test_state["completed"] = True
                    st.rerun()

    # After all questions are answered, evaluate the result
    if test_state["completed"]:
        correct_answers = 0
        candidate_answers = test_state["answers"]

        # Calculate the score
        for i, mcq in enumerate(role_mcqs):
            if mcq["answer"] == candidate_answers[i]:
                correct_answers += 1

        total_questions = len(role_mcqs)
        passing_score = 0.7  # 70%
        score_percentage = (correct_answers / total_questions) * 100

        # Display the result
        st.write(f"Test completed! You answered {correct_answers} out of {total_questions} questions correctly.")
        st.write(f"Your score: {score_percentage:.2f}%")

        st.session_state.test_conducted = True
        if score_percentage >= (passing_score * 100):
            st.success("You have passed the test!")
            return True
        else:
            st.error("You did not pass the test.")
            return False

def update_analytics(role, test_result):
    """
    Updates the analytics.json file based on the test result.

    Args:
        role (str): The role of the candidate.
        test_result (bool): True if the candidate passed the test, False otherwise.
    """
    try:
        with open('analytics.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"roles": {}, "interviews": []}

    # Ensure the role exists in the data
    if role not in data["roles"]:
        data["roles"][role] = {"total_applicants": 0, "selected_for_test": 0, "passed": 0, "failed": 0}

    # Increment selected_for_test
    data["roles"][role]["selected_for_test"] += 1

    # Increment passed or failed count based on the test result
    if test_result:
        data["roles"][role]["passed"] += 1
    else:
        data["roles"][role]["failed"] += 1

    # Write the updated data back to the analytics.json file
    with open('analytics.json', 'w') as f:
        json.dump(data, f, indent=4)

# Example usage:
# update_analytics("AI/ML Engineer", True)


def main() -> None:
    st.title("AI Recruitment System")

    init_session_state()
    with st.sidebar:
        st.header("Configuration")
        
        if st.sidebar.button("Show Analytics" if not st.session_state["show_analytics"] else "Back to Recruitment"):
            st.session_state["show_analytics"] = not st.session_state["show_analytics"]
            st.rerun()

        # OpenAI Configuration
        st.subheader("OpenAI Settings")
        api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state.openai_api_key, help="Get your API key from platform.openai.com")
        if api_key: st.session_state.openai_api_key = api_key
        else: st.session_state.openai_api_key = "sk-1234567890abcdef1234567890abcdef"

        st.subheader("Zoom Settings")
        zoom_account_id = st.text_input("Zoom Account ID", type="password", value=st.session_state.zoom_account_id)
        zoom_client_id = st.text_input("Zoom Client ID", type="password", value=st.session_state.zoom_client_id)
        zoom_client_secret = st.text_input("Zoom Client Secret", type="password", value=st.session_state.zoom_client_secret)
        
        st.subheader("Email Settings")
        email_sender = st.text_input("Sender Email", value=st.session_state.email_sender, help="Email address to send from")
        recruiter_email = st.text_input("Recruiter Email", value=st.session_state.recruiter_email, help="Email address to send to as a recruiter")
        email_passkey = st.text_input("Email App Password", type="password", value=st.session_state.email_passkey, help="App-specific password for email")
        company_name = st.text_input("Company Name", value=st.session_state.company_name, help="Name to use in email communications")

        if zoom_account_id:
            st.session_state.zoom_account_id = zoom_account_id
        else:
            st.session_state.zoom_account_id = "Ad5Btk3mQ2S9n39sTys4Qg"

        if zoom_client_id:
            st.session_state.zoom_client_id = zoom_client_id
        else:
            st.session_state.zoom_client_id = "6RezhEmWQ7qVGwGrUKuPMQ"
        if zoom_client_secret:
            st.session_state.zoom_client_secret = zoom_client_secret
        else:
            st.session_state.zoom_client_secret = "woLGmXOtR4PAtfPDQfoy9JWkWOUoo5lK"
        if email_sender:
            st.session_state.email_sender = email_sender
        else:
            st.session_state.email_sender = "setooproject00@gmail.com"

        if email_passkey:
            st.session_state.email_passkey = email_passkey
        else:
            st.session_state.email_passkey = "kpcxquihonbqissr"

        if company_name:
            st.session_state.company_name = company_name
        else:
            st.session_state.company_name = "Setoo"
        if recruiter_email: 
            st.session_state.recruiter_email = recruiter_email
        else:
            st.session_state.recruiter_email = "setodkar6@gmail.com"

        
        final_roles = manage_roles()
        schedule_meeting()
        st.sidebar.subheader("Manage Interview Slots")
        st.subheader("Available Slots for Self-Scheduling Interviews")

        # Define the path to the predefined times file
        predefined_times_path = r"C:\Users\Admin\python_project\awesome-llm-apps\ai_agent_tutorials\ai_recruitment_agent_team\predefined_times.json"

        # Load available times into session state
        if "available_times" not in st.session_state:
            try:
                with open(predefined_times_path, "r") as file:
                    predefined_data = json.load(file)
                    st.session_state.available_times = predefined_data.get("available_times", [])
            except FileNotFoundError:
                st.session_state.available_times = []

        # Display current available slots
        st.write("Current Available Slots:")
        for i, slot in enumerate(st.session_state.available_times):
            st.write(f"{i + 1}. {slot}")

        # Add a new slot
        with st.form("add_slot_form"):
            st.write("Add a New Slot")
            new_date = st.date_input("New Slot Date:", key="add_date")
            new_time = st.time_input("New Slot Time:", key="add_time")
            add_slot = st.form_submit_button("Add Slot")

            if add_slot and new_date and new_time:
                new_slot = f"{new_date} {new_time}"
                if new_slot not in st.session_state.available_times:
                    st.session_state.available_times.append(new_slot)
                    st.rerun()
                    st.success(f"Slot {new_slot} added successfully!")
                else:
                    st.rerun()
                    st.warning("This slot already exists.")
                
        # Remove an existing slot
        with st.form("remove_slot_form"):
            st.write("Remove an Existing Slot")
            if st.session_state.available_times:
                slot_to_remove = st.selectbox("Select Slot to Remove:", options=st.session_state.available_times, key="remove_slot")
                remove_slot = st.form_submit_button("Remove Slot")

                if remove_slot and slot_to_remove:
                    st.session_state.available_times.remove(slot_to_remove)
                    st.rerun()
                    st.success(f"Slot {slot_to_remove} removed successfully!")
            else:
                st.info("No available slots to remove.")

        # Save updated slots to the JSON file
        with open(predefined_times_path, "w") as file:
            json.dump({"available_times": st.session_state.available_times}, file, indent=4)

        st.write("Changes saved successfully!")


        required_configs = {'OpenAI API Key': st.session_state.openai_api_key, 'Zoom Account ID': st.session_state.zoom_account_id,
                          'Zoom Client ID': st.session_state.zoom_client_id, 'Zoom Client Secret': st.session_state.zoom_client_secret,
                          'Email Sender': st.session_state.email_sender, 'Email Password': st.session_state.email_passkey,
                          'Company Name': st.session_state.company_name}
        

    if st.session_state["show_analytics"]:
        display_analytics()

    missing_configs = [k for k, v in required_configs.items() if not v]
    if missing_configs:
        st.warning(f"Please configure the following in the sidebar: {', '.join(missing_configs)}")
        return

    if not st.session_state.openai_api_key and  not st.session_state["show_analytics"]:
        st.warning("Please enter your OpenAI API key in the sidebar to continue.")
        return
    
    if not st.session_state["show_analytics"]:
        role = st.selectbox("Select the role you're applying for:", list(final_roles.keys()))
        with st.expander("View Required Skills", expanded=True): st.markdown(final_roles[role])

    if not st.session_state["show_analytics"]:
        # Add a "New Application" button before the resume upload
        if st.button("📝 New Application") :
            # Clear only the application-related states
            keys_to_clear = ['resume_text', 'analysis_complete', 'is_selected', 'candidate_email', 'current_pdf']
            for key in keys_to_clear:
                st.session_state[key] = None if key == 'current_pdf' else ""

            # Reset session state flags
            reset_flags = ['fragment', 'check_it', 'analysis_complete', 'is_selected', 'proceed_app', 'test_conducted', 
                        'time_change_requested', 'go_ahead', 'session_to_proceed', 'check_again', 'no_button', 'time_and_date']
            for flag in reset_flags:
                st.session_state[flag] = False
            st.rerun()

        resume_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"], key="resume_uploader")
        if resume_file is not None and resume_file != st.session_state.get('current_pdf') and not st.session_state["show_analytics"]:
            st.session_state.current_pdf = resume_file
            st.session_state.resume_text = ""
            st.session_state.analysis_complete = False
            st.session_state.is_selected = False
            st.rerun()

        if resume_file  and not st.session_state["show_analytics"]:
            st.subheader("Uploaded Resume")
            col1, col2 = st.columns([4, 1])
            
            with col1:
                import tempfile, os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(resume_file.read())
                    tmp_file_path = tmp_file.name
                resume_file.seek(0)
                try: pdf_viewer(tmp_file_path)
                finally: os.unlink(tmp_file_path)
            
            with col2:
                st.download_button(label="📥 Download", data=resume_file, file_name=resume_file.name, mime="application/pdf")
            # Process the resume text
            if not st.session_state.resume_text  and not st.session_state["show_analytics"]:
                with st.spinner("Processing your resume..."):
                    resume_text = extract_text_from_pdf(resume_file)
                    if resume_text:
                        st.session_state.resume_text = resume_text
                        st.success("Resume processed successfully!")
                    else:
                        st.error("Could not process the PDF. Please try again.")

        # Email input with session state
        email_can = st.text_input(
            "Candidate's email address",
            value=st.session_state.candidate_email,
            key="email_input"
        )
        if email_can  and not st.session_state["show_analytics"]:
            st.session_state.candidate_email = email_can
        else:
            st.session_state.candidate_email = "setodkar06@gmail.com"

        if st.session_state.resume_text and st.session_state.candidate_email and not st.session_state.analysis_complete and not st.session_state["show_analytics"]:
            if st.button("Analyze Resume"):
                with st.spinner("Analyzing your resume..."):
                    print("DEBUG: Starting resume analysis")
                    is_selected, feedback = analyze_resume(
                        st.session_state.resume_text,
                        role
                    )
                    print(f"DEBUG: Analysis complete - Selected: {is_selected}, Feedback: {feedback}")

                    # Update total applicants for the role in analytics.json
                    try:
                        with open('analytics.json', 'r') as f:
                            try:
                                data = json.load(f)
                            except json.JSONDecodeError:
                                data = {"roles": {}, "interviews": []}
                    except FileNotFoundError:
                        data = {"roles": {}, "interviews": []}

                    if role not in data["roles"]:
                        data["roles"][role] = {"total_applicants": 0, "selected_for_test": 0, "passed": 0, "failed": 0}

                    data["roles"][role]["total_applicants"] += 1

                    with open('analytics.json', 'w') as f:
                        json.dump(data, f, indent=4)

                    if is_selected:
                        st.success("Congratulations! Your skills match our requirements.")
                        st.session_state.analysis_complete = True
                        st.session_state.is_selected = True
                        st.rerun()
                    else:
                        st.warning("Unfortunately, your skills don't match our requirements.")
                        st.write(f"Feedback: {feedback}")
                                
                        # Send rejection email
                        with st.spinner("Sending feedback email..."):
                            try:
                                send_rejection_email(st.session_state.get('email_sender'),
                                                    st.session_state.get('email_passkey'), 
                                                    st.session_state.get('candidate_email'),
                                                    role, 
                                                    st.session_state.get('company_name'))
                                st.info("We've sent you an email with detailed feedback.")
                            except Exception as e:
                                logger.error(f"Error sending rejection email: {e}")
                                st.error("Could not send feedback email. Please try again.")



    if st.session_state.get('analysis_complete') and st.session_state.get('is_selected', False) and not st.session_state.get('proceed_app') and not st.session_state["show_analytics"]:
        test_result = conduct_test_and_evaluate(role)

        if test_result:
            st.session_state.go_ahead = True    
        else:
            st.session_state.go_ahead = False
            
    if st.session_state.get('test_conducted') and not st.session_state.get('go_ahead') and st.session_state.get('is_selected', False)  and not st.session_state["show_analytics"]:
        update_analytics(role, st.session_state.get('go_ahead'))
        st.error("You need to pass the test to proceed with the application.")
        st.info("Unfortunately we are unable to proceed.")
        with st.spinner("Sending feedback email..."):
                            try:
                                send_rejection_email(st.session_state.get('email_sender'),
                                                     st.session_state.get('email_passkey'), 
                                                     st.session_state.get('candidate_email'),
                                                     role, 
                                                     st.session_state.get('company_name'),
                                                     )
                                test_state_key = f"{role}_test_state"
                                if test_state_key in st.session_state:
                                        st.session_state[test_state_key] = {
                                            "progress": 0,
                                            "answers": [],
                                            "completed": False
                                        }
                                st.info("We've sent you an email with detailed feedback.")
                            except Exception as e:
                                logger.error(f"Error sending rejection email: {e}")
                                st.error("Could not send feedback email. Please try again.")
    if st.session_state.get('test_conducted') and st.session_state.get('analysis_complete') and st.session_state.get('is_selected', False) and st.session_state.go_ahead and not st.session_state.get('session_to_proceed')  and not st.session_state["show_analytics"]:
        update_analytics(role, st.session_state.get('go_ahead'))
        test_state_key = f"{role}_test_state"
        if test_state_key in st.session_state:
                st.session_state[test_state_key] = {
                    "progress": 0,
                    "answers": [],
                    "completed": False
                }
        st.success("Congratulations! You have passed the test")
        st.info("Click 'Proceed with Application' to continue with the interview process.")
        
        if st.button("Proceed with Application", key="proceed_button"):
            print("DEBUG: Proceed button clicked")  # Debug
            with st.spinner("🔄 Processing your application..."):
                try:
                    # 3. Send selection email
                    with st.status("📧 Sending confirmation email...", expanded=True) as status:
                        print(f"DEBUG: Attempting to send email to {st.session_state.candidate_email}")  # Debug
                        send_selection_email(
                           st.session_state.get('email_sender'),
                           st.session_state.get('email_passkey'),
                           st.session_state.get('candidate_email'), 
                           role, 
                           st.session_state.get('company_name'))
                        print("DEBUG: Email sent successfully")  # Debug
                        status.update(label="✅ Confirmation email sent!")

                    st.session_state.session_to_proceed = True
                    st.session_state.proceed_app = True
                    
                    # 4. Schedule interview
                    with st.status("📅 Scheduling interview...", expanded=True):
                        print("DEBUG: Attempting to schedule interview")  # Debug

                    st.rerun()

                except Exception as e:
                    print(f"DEBUG: Error occurred: {str(e)}")  # Debug
                    print(f"DEBUG: Error type: {type(e)}")  # Debug
                    import traceback
                    print(f"DEBUG: Full traceback: {traceback.format_exc()}")  # Debug
                    st.error(f"An error occurred: {str(e)}")
                    st.error("Please try again or contact support.")
                    

    if not st.session_state.get('no_button') and st.session_state.get('proceed_app')  and not st.session_state["show_analytics"]:
        st.success("Confimation email sent successfully!")
        st.info("Schedule interview time out of given time!")
        st.session_state.time_change_requested = ask_for_time_change()
        st.session_state.check_again = True

    if st.session_state.get('time_change_requested') and not st.session_state.get('time_and_date')  and not st.session_state["show_analytics"]:
        st.session_state.check_it = True
        update_meeting_schedule() 
    else:
        st.session_state.check_it = True

    if st.session_state.get('check_it')  and not st.session_state["show_analytics"] and st.session_state.get('check_again') and not st.session_state.get('fragment'):
        if st.button("Proceed with Schedule", key="schedule_button"):
            st.session_state.no_button = True
            st.session_state.time_and_date = True
            schedule_interview(
                st.session_state.get('zoom_account_id'),
                st.session_state.get('zoom_client_id'),
                st.session_state.get('zoom_client_secret'),
                st.session_state.get('email_sender'),
                st.session_state.get('email_passkey'),
                st.session_state.get('candidate_email'),
                st.session_state.get('recruiter_email'),
                role,
                st.session_state.get('company_name'),
                "UTC"
            )
            st.session_state.fragment = True
            st.rerun()

    if st.session_state.get('fragment') and not st.session_state["show_analytics"]:
        st.success("Interview scheduled successfully! Check your email for details.")
        st.info("Interview scheduled and email sent successfully.")
        print("DEBUG: All processes completed successfully")  # Debug
        st.success("""
            🎉 Application Successfully Processed!
            
            Please check your email for:
            1. Selection confirmation ✅
            2. Interview details with Zoom link 🔗
            
            Next steps:
            1. Review the role requirements
            2. Prepare for your technical interview
            3. Join the interview 5 minutes early
        """)

    if st.sidebar.button("Reset Application"):
        # Clear all session state keys except 'openai_api_key'
        for key in st.session_state.keys():
            if key != 'openai_api_key':
                del st.session_state[key]
        
        # Load roles dynamically from roles.json
        try:
            with open('roles.json', 'r') as f:
                roles_data = json.load(f)
        except FileNotFoundError:
            st.error("The file 'roles.json' was not found.")
            return  # You can remove this return if you don't want to exit the function
        except json.JSONDecodeError:
            st.error("Error decoding 'roles.json'. Please check the file format.")
            return  # Similarly, remove return here if you don't want to exit the function
        
        # Initialize analytics.json with dynamic roles and default values
        initial_data = {"roles": {}, "interviews": []}
        
        # Iterate over roles and initialize the corresponding analytics data
        for role in roles_data:
            # Convert role names to a format consistent with the analytics (e.g., "AI/ML Engineer" from "ai_ml_engineer")
            formatted_role = role.replace('_', ' ').title()
            initial_data["roles"][formatted_role] = {
                "total_applicants": 0,
                "selected_for_test": 0,
                "passed": 0,
                "failed": 0
            }
        
        # Write the initialized data back to the analytics.json file
        with open('analytics.json', 'w') as f:
            json.dump(initial_data, f, indent=4)

        st.rerun()

if __name__ == "__main__":
    main()