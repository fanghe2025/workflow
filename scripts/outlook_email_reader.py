from exchangelib import Credentials, Account, Configuration

# Set up credentials and access the Outlook account
email = "your_email@outlook.com"
password = "your_app_password"  # Use app password if 2FA is enabled

# Create the credentials object
credentials = Credentials(username=email, password=password)

# Manually configure the server if autodiscover fails
config = Configuration(server='outlook.office365.com')  # Use Office 365's server if you're using it

try:
    # Connect to the account (disable autodiscover)
    
    account = Account(email, credentials=credentials, autodiscover=True)
    # account = Account(email, credentials=credentials, config=config, autodiscover=False)

    # Print out the folders to ensure the connection was successful
    # print("Available Folders:")
    # for folder in account.folders:
    #     print(folder.name)

    # Try accessing the inbox folder
    inbox = account.inbox
    print(f"Accessing inbox: {inbox}")

except Exception as e:
    print(f"Error: {e}")

# Define the label (this will be the tag you add)
tag = "Important"

# Get the first 10 emails
emails = inbox.all().order_by('-datetime_received')[:10]

# Read and add a tag to each email
for email in emails:
    print(f"Subject: {email.subject}")
    print(f"From: {email.sender}")
    print(f"Received: {email.datetime_received}")
    
    # Print the email body
    print(f"Body: {email.body}")
    
    # Add a tag by categorizing the email (if using Exchange/Outlook categories)
    email.categories = [tag]  # Add the tag as a category
    email.save()  # Save changes to the email

    print(f"Tag '{tag}' added to the email.")

# Optional: Send a response or perform other actions here if necessary
