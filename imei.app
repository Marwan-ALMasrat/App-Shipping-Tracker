
import pandas as pd
import streamlit as st
import numpy as np
import traceback
import time
import os
import tempfile
import urllib.request

st.set_page_config(page_title="Returns Tracker (IMEI)", layout="wide")

def fetch_excel_file():
    """
    Downloads the Excel file from Google Sheets and saves it to a temporary location.
    Returns the path to the downloaded file.
    """
    try:
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.close()
        
        # URL to the Google Sheet (with timestamp to prevent caching)
        timestamp = int(time.time())
        url = f'https://docs.google.com/spreadsheets/d/1Khq4LytjOgY0vN-LTO9MSp7smRQP35hP/export?format=xlsx&_ts={timestamp}'
        
        # Download the file
        urllib.request.urlretrieve(url, temp_file.name)
        
        # Log the download
        st.sidebar.success(f"Downloaded Excel file at {time.strftime('%H:%M:%S')}")
        
        return temp_file.name
    except Exception as e:
        st.error(f"Failed to download Excel file: {e}")
        return None

def load_data():
    """
    Loads data from the downloaded Excel file.
    """
    try:
        # Get the file path
        file_path = fetch_excel_file()
        
        if not file_path or not os.path.exists(file_path):
            st.error("Could not download the Excel file.")
            return pd.DataFrame()
        
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        # Clean up the temporary file
        try:
            os.unlink(file_path)
        except:
            pass
        
        # Drop unnecessary columns
        cols_to_drop = [col for col in df.columns if 'Unnamed: 34' in col or 'Unnamed: 0' in col or 'Dispute' in col]
        df = df.drop(cols_to_drop, axis=1, errors='ignore')
        
        # Convert IMEI column to string and clean it
        if 'IMEI' in df.columns:
            df['IMEI'] = df['IMEI'].astype(str).str.replace('.0', '')
            
        # Display sample IMEI for verification
        if not df.empty and 'IMEI' in df.columns:
            st.sidebar.write(f"Number of records: {len(df)}")
            st.sidebar.write(f"Sample IMEI: {df['IMEI'].iloc[0]}")
            st.sidebar.write(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.sidebar.text(traceback.format_exc())
        return pd.DataFrame()

# Search function
def search_imei(imei_value, df):
    """
    Search for IMEI in the dataframe and return appropriate response
    Returns:
    - "short" (string): if IMEI is too short
    - None: if IMEI not found
    - dict: if IMEI found (converted from Series to dict)
    """
    # Check if IMEI column exists
    if 'IMEI' not in df.columns:
        st.error("IMEI column not found in the data!")
        return None
    
    # Clean IMEI value
    imei_str = str(imei_value).strip().replace('.0', '')
    
    # Debug information
    st.sidebar.write(f"Searching for: {imei_str}")
    if not df.empty:
        sample_values = df['IMEI'].head(3).tolist()
        st.sidebar.write(f"Sample values in IMEI column: {sample_values}")
    
    # Check IMEI length
    if len(imei_str) < 15:
        return "short"  # Return a string, not a Series
    
    # Find exact match
    matches = df[df['IMEI'] == imei_str]
    
    if len(matches) > 0:
        # Convert Series to dict to avoid comparison issues
        return matches.iloc[0].to_dict()
    else:
        # Try more flexible search
        flexible_matches = df[df['IMEI'].str.contains(imei_str, na=False)]
        if len(flexible_matches) > 0:
            return flexible_matches.iloc[0].to_dict()
        return None

# Format value function - handles various data types
def format_value(key, value):
    if pd.isna(value):
        return 'Not available'
    
    # Check if it could be a financial value
    financial_keywords = ['cost', 'price', 'amount', 'fee', 'value', 'tax', 'refund', 'shipping', 'total']
    is_financial = any(keyword in key.lower() for keyword in financial_keywords)
    
    if is_financial:
        try:
            return f"${float(value):.2f}"
        except:
            return value
    
    # Format date values
    date_keywords = ['date', 'time']
    is_date = any(keyword in key.lower() for keyword in date_keywords)
    
    if is_date:
        try:
            if isinstance(value, pd.Timestamp):
                return value.strftime('%Y-%m-%d')
            return value
        except:
            return value
    
    # Default return
    return value

# Main app
st.title('Returns Tracker (IMEI)')

# Add a button to force data refresh
if st.sidebar.button('⟳ Refresh Data', key='refresh_button'):
    st.experimental_rerun()  # Force a complete rerun of the app

# Load data directly
df = load_data()

# Show progress indicator
if df.empty:
    st.warning("Data was not loaded correctly. Please check the URL.")
else:
    st.success(f"Successfully loaded {len(df)} records")

# IMEI input
imei = st.text_input('Enter IMEI number to search:', value='354653661425023')

if st.button('Search'):
    if df.empty:
        st.error("Cannot search. Data not available!")
    else:
        try:
            imei_value = imei.strip()
            result = search_imei(imei_value, df)
            
            # Use isinstance() for type checking instead of equality comparison
            if result is None:
                st.error(f'IMEI not found: {imei_value}!')
                
                # Show sample IMEI values for troubleshooting
                if 'IMEI' in df.columns:
                    st.write("Some available IMEI values for search:")
                    imei_examples = df['IMEI'].head(5).tolist()
                    for i, ex in enumerate(imei_examples):
                        st.write(f"{i+1}. {ex}")
                
            elif result == "short":  # Safe comparison as result is now guaranteed to be a string or dict
                st.warning('IMEI number must have at least 15 digits!')
            else:
                # Display shipping and delivery information
                delivery_status = result.get('Status.1', 'Unknown')
                
                # Create delivery status indicator
                if delivery_status == 'DELIVERED':
                    status_color = 'green'
                    icon = '✅'
                elif delivery_status == 'IN TRANSIT':
                    status_color = 'blue'
                    icon = '🚚'
                else:
                    status_color = 'orange'
                    icon = '⏳'
                
                # Show delivery status prominently
                st.markdown(f"""
                <div style='background-color: #f0f0f0; padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
                    <h2 style='text-align: center; color: {status_color};'>{icon} Delivery Status: {delivery_status}</h2>
                </div>
                """, unsafe_allow_html=True)
                
                # Organize data into categories
                categories = {
                    'Product Information': ['Store ID', 'Store', 'Item ', 'SKU', 'IMEI', 'Exchange IMEI', 'Status'],
                    'Shipping Details': ['Tracking number', 'Status.1', 'Unnamed: 20', 'Unnamed: 21', 'Unnamed: 22'],
                    'Financial Information': ['Cost', 'Price', 'Refund', 'Exchange Price', 'Total', 'Tax', 'Restocking Fee', 'Shipping'],
                    'Return Information': ['Return Invoice', 'Return Date', 'Case Number', 'Name', 'Original Invoice', 'Original Date'],
                    'Additional Information': []  # Will catch all remaining fields
                }
                
                # Create a set of keys that are already assigned to specific categories
                assigned_keys = set()
                for cat_keys in categories.values():
                    assigned_keys.update(cat_keys)
                
                # Assign all remaining keys to Additional Information
                for key in result.keys():
                    if key not in assigned_keys:
                        categories['Additional Information'].append(key)
                
                # Display all data by category
                for category, fields in categories.items():
                    if fields:  # Only show categories with fields
                        st.subheader(category)
                        
                        # Create a three-column layout for more compact display
                        if category != 'Additional Information':  # Regular categories use columns
                            cols = st.columns(3)
                            for i, field in enumerate(fields):
                                if field in result:
                                    value = format_value(field, result[field])
                                    # Replace cryptic column names with more readable ones
                                    display_name = field
                                    if field == 'Unnamed: 20':
                                        display_name = 'Shipping Company'
                                    elif field == 'Unnamed: 21':
                                        display_name = 'Delivery Date'
                                    elif field == 'Unnamed: 22':
                                        display_name = 'Delivery Location'
                                    elif field == 'Status.1':
                                        display_name = 'Delivery Status'
                                    
                                    cols[i % 3].write(f"**{display_name}:** {value}")
                        else:  # Additional Information uses full width
                            for field in fields:
                                if field in result:
                                    value = format_value(field, result[field])
                                    st.write(f"**{field}:** {value}")
                
                # Tracking link if available
                tracking_link = result.get('Link', '')
                if pd.notna(tracking_link) and tracking_link:
                    st.markdown(f"[Tracking Link]({tracking_link})")
        
        except Exception as e:
            st.error(f'An error occurred: {e}')
            st.sidebar.text(traceback.format_exc())
            st.error('Please verify the IMEI number and data format')

# Add option to display raw data for troubleshooting
if st.sidebar.checkbox("Show Raw Data"):
    st.sidebar.dataframe(df.head())
    
    if 'IMEI' in df.columns:
        st.sidebar.subheader("Sample IMEI values:")
        st.sidebar.write(df['IMEI'].head(10).tolist())
        
    # Display all column names for troubleshooting
    st.sidebar.subheader("All available columns:")
    st.sidebar.write(df.columns.tolist())
