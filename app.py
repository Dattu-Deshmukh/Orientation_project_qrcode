import streamlit as st
import cv2
from pyzbar.pyzbar import decode
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Google Sheets authentication
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Open Google Sheet
sheet = client.open("orientation_passes").sheet1

st.title("📷 Orientation Program QR Scanner")

# Camera capture
camera = cv2.VideoCapture(0)

if st.button("Start Scanner"):
    while True:
        ret, frame = camera.read()
        if not ret:
            st.error("Camera not available")
            break

        for code in decode(frame):
            qr_data = code.data.decode("utf-8")
            st.write(f"Scanned ID: {qr_data}")

            try:
                records = sheet.get_all_records()
                found = False
                for i, row in enumerate(records, start=2):
                    if str(row["ID"]) == qr_data:
                        found = True
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        if row["EntryStatus"] == "":
                            sheet.update_cell(i, 4, "Entered")
                            sheet.update_cell(i, 5, now)
                            st.success(f"✅ Entry marked for {row['Name']}")
                        elif row["ExitStatus"] == "":
                            sheet.update_cell(i, 6, "Exited")
                            sheet.update_cell(i, 7, now)
                            st.success(f"🚪 Exit marked for {row['Name']}")
                        else:
                            st.info(f"ℹ️ Already entered and exited: {row['Name']}")
                        break

                if not found:
                    st.error("❌ ID not found in records")

            except Exception as e:
                st.error(f"Error: {e}")

        cv2.imshow("QR Scanner", frame)
        if cv2.waitKey(1) == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()
