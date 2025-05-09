import pandas as pd
import streamlit as st
import numpy as np
import traceback
import time
import os
import tempfile
import urllib.request
import logging
import re
import requests
from functools import lru_cache

# إعداد التسجيل
logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

st.set_page_config(page_title="Returns Tracker (IMEI)", layout="wide")

def clean_imei(imei_value):
    """تنظيف قيمة IMEI وإعادتها كسلسلة نصية مع الحفاظ على الأصفار."""
    try:
        if imei_value is None or pd.isna(imei_value):
            return ""
            
        # التحويل إلى سلسلة نصية
        imei_str = str(imei_value).strip()
        
        # إزالة الكسور العشرية (.0) إذا وجدت
        if imei_str.endswith('.0'):
            imei_str = imei_str[:-2]
            
        # التأكد من أن IMEI يتم معالجته كنص وليس كرقم للحفاظ على الأصفار
        return imei_str
    except Exception as e:
        logging.error(f"Error cleaning IMEI {imei_value}: {e}")
        return ""

def extract_file_id_from_url(url):
    """استخراج معرف الملف من رابط Google Drive."""
    # النمط الأول: /d/FILE_ID/
    pattern1 = r"/d/([a-zA-Z0-9_-]+)"
    # النمط الثاني: id=FILE_ID
    pattern2 = r"id=([a-zA-Z0-9_-]+)"
    
    match = re.search(pattern1, url)
    if match:
        return match.group(1)
    
    match = re.search(pattern2, url)
    if match:
        return match.group(1)
    
    return None

@st.cache_data(ttl=300)  # تحديث كل 5 دقائق
def fetch_excel_file(timestamp):
    """
    تنزيل ملف Excel من Google Drive وحفظه في موقع مؤقت.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            # رابط Google Drive
            url = 'https://docs.google.com/spreadsheets/d/1vTa0AAqVztj9gSQb2r-OsTc1uHu6dC8n/edit?usp=drive_link&ouid=114445506269373692681&rtpof=true&sd=true'
            
            # استخراج معرف الملف
            file_id = extract_file_id_from_url(url)
            if not file_id:
                st.sidebar.error("Could not extract file ID from the URL")
                return None
            
            # رابط التنزيل المباشر من Google Drive
            download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
            
            st.sidebar.info(f"Attempting to download file using ID: {file_id}")
            
            # تنزيل الملف باستخدام مكتبة requests
            response = requests.get(download_url)
            if response.status_code != 200:
                st.sidebar.error(f"Failed to download file: HTTP status {response.status_code}")
                return None
            
            # كتابة المحتوى إلى الملف المؤقت
            with open(temp_file.name, 'wb') as f:
                f.write(response.content)
            
            # التحقق من حجم الملف
            file_size = os.path.getsize(temp_file.name)
            if file_size < 1024:  # الملف أقل من 1KB يعتبر غير صالح
                st.sidebar.error(f"Downloaded file is too small: {file_size} bytes")
                raise ValueError("Downloaded file is too small or empty")
                
            st.sidebar.success(f"Downloaded Excel file at {time.strftime('%H:%M:%S')} - Size: {file_size/1024:.2f} KB")
            return temp_file.name
    except Exception as e:
        logging.error(f"Failed to download Excel file: {e}")
        st.sidebar.error(f"Failed to download Excel file: {str(e)}")
        return None

def load_data():
    """تحميل البيانات من ملف Excel."""
    try:
        timestamp = int(time.time())
        file_path = fetch_excel_file(timestamp)
        
        if not file_path or not os.path.exists(file_path):
            st.error("Could not download the Excel file.")
            return pd.DataFrame()
        
        # عرض معلومات عن الملف قبل القراءة
        file_size = os.path.getsize(file_path)
        st.sidebar.info(f"File size: {file_size/1024:.2f} KB")
        
        try:
            # محاولة قراءة الملف
            df = pd.read_excel(file_path)
            
            # التحقق من البيانات
            if df.empty:
                st.sidebar.warning("DataFrame is empty after loading")
            else:
                st.sidebar.success(f"DataFrame loaded with {len(df)} rows and {len(df.columns)} columns")
        except Exception as excel_error:
            logging.error(f"Error reading Excel file: {excel_error}")
            st.error(f"Error reading Excel file: {excel_error}")
            st.sidebar.error(traceback.format_exc())
            return pd.DataFrame()
        
        # تنظيف الملف المؤقت
        try:
            os.unlink(file_path)
        except Exception as del_error:
            logging.warning(f"Failed to delete temporary file: {file_path}, error: {del_error}")
        
        # إزالة الأعمدة غير الضرورية
        cols_to_drop = [col for col in df.columns if 'Unnamed: 34' in col or 'Unnamed: 0' in col or 'Dispute' in col]
        df = df.drop(cols_to_drop, axis=1, errors='ignore')
        
        # التأكد من أن عمود IMEI يتم قراءته كنص وليس كرقم
        if 'IMEI' in df.columns:
            # تحويل عمود IMEI إلى نوع نصي أثناء القراءة
            df['IMEI'] = df['IMEI'].astype(str)
            # تنظيف عمود IMEI مع الحفاظ على الأصفار
            df['IMEI'] = df['IMEI'].apply(clean_imei)
        else:
            st.sidebar.warning("IMEI column not found in the DataFrame!")
            st.sidebar.write("Available columns:", df.columns.tolist())
        
        # عرض معلومات التتبع
        if not df.empty and 'IMEI' in df.columns:
            st.sidebar.write(f"Number of records: {len(df)}")
            st.sidebar.write(f"Sample IMEI: {df['IMEI'].iloc[0]}")
            st.sidebar.text(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return df
    except Exception as e:
        logging.error(f"Error loading data: {e}")
        st.error(f"Error loading data: {e}")
        st.sidebar.text(traceback.format_exc())
        return pd.DataFrame()

def search_imei(imei_value, df):
    """البحث عن IMEI في البيانات."""
    if 'IMEI' not in df.columns:
        st.error("IMEI column not found in the data!")
        return None
    
    imei_str = clean_imei(imei_value)
    
    # معلومات تصحيح الأخطاء
    st.sidebar.text(f"Searching for: {imei_str}")
    if not df.empty:
        sample_values = df['IMEI'].head(3).tolist()
        st.sidebar.text(f"Sample values in IMEI column: {sample_values}")
    
    # التحقق من طول IMEI
    if len(imei_str) < 15:
        return "short"
    
    # البحث الدقيق
    matches = df[df['IMEI'] == imei_str]
    
    if len(matches) > 0:
        return matches.iloc[0].to_dict()
    
    # البحث المرن (مع التحقق من القيم الفارغة)
    try:
        flexible_matches = df[df['IMEI'].str.contains(imei_str, na=False)]
        if len(flexible_matches) > 0:
            return flexible_matches.iloc[0].to_dict()
    except Exception as e:
        logging.warning(f"Flexible search failed: {e}")
    
    return None

def format_value(key, value):
    """تنسيق القيم بناءً على نوع البيانات."""
    if pd.isna(value):
        return 'Not available'
    
    financial_keywords = ['cost', 'price', 'amount', 'fee', 'value', 'tax', 'refund', 'shipping', 'total']
    is_financial = any(keyword in key.lower() for keyword in financial_keywords)
    
    if is_financial:
        try:
            return f"${float(value):.2f}"
        except:
            return value
    
    date_keywords = ['date', 'time']
    is_date = any(keyword in key.lower() for keyword in date_keywords)
    
    if is_date:
        try:
            if isinstance(value, pd.Timestamp):
                return value.strftime('%Y-%m-%d')
            return value
        except:
            return value
    
    return value

# التطبيق الرئيسي
st.title('Returns Tracker (IMEI)')

# إضافة حقل إدخال الرابط
default_url = 'https://docs.google.com/spreadsheets/d/1vTa0AAqVztj9gSQb2r-OsTc1uHu6dC8n/edit?usp=drive_link&ouid=114445506269373692681&rtpof=true&sd=true'
excel_url = st.sidebar.text_input('Google Drive URL:', value=default_url)

# زر تحديث البيانات
if st.sidebar.button('⟳ Refresh Data', key='refresh_button'):
    st.cache_data.clear()  # مسح ذاكرة التخزين المؤقت
    st.experimental_rerun()

# تحميل البيانات
with st.spinner('Loading data...'):
    df = load_data()

# عرض مؤشر التقدم
if df.empty:
    st.warning("Data was not loaded correctly. Please check the URL or file format.")
else:
    st.success(f"Successfully loaded {len(df)} records")

# إدخال IMEI
imei = st.text_input('Enter IMEI number to search:', value='354653661425023')

if st.button('Search'):
    if df.empty:
        st.error("Cannot search. Data not available!")
    else:
        try:
            result = search_imei(imei, df)
            
            if result is None:
                st.error(f'IMEI not found: {imei}!')
                if 'IMEI' in df.columns:
                    st.write("Some available IMEI values for search:")
                    imei_examples = df['IMEI'].head(5).tolist()
                    for i, ex in enumerate(imei_examples):
                        st.write(f"{i+1}. {ex}")
                
            elif result == "short":
                st.warning('IMEI number must have at least 15 digits!')
            else:
                delivery_status = result.get('Status.1', 'Unknown')
                
                # تحديد حالة التسليم
                if delivery_status == 'DELIVERED':
                    status_color = 'green'
                    icon = '✅'
                elif delivery_status == 'IN TRANSIT':
                    status_color = 'blue'
                    icon = '🚚'
                else:
                    status_color = 'orange'
                    icon = '⏳'
                
                # عرض حالة التسليم
                st.markdown(f"""
                <div style='background-color: #f0f0f0; padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
                    <h2 style='text-align: center; color: {status_color};'>{icon} Delivery Status: {delivery_status}</h2>
                </div>
                """, unsafe_allow_html=True)
                
                # تنظيم البيانات في فئات
                categories = {
                    'Product Information': ['Store ID', 'Store', 'Item ', 'SKU', 'IMEI', 'Exchange IMEI', 'Status'],
                    'Shipping Details': ['Tracking number', 'Status.1', 'Unnamed: 20', 'Unnamed: 21', 'Unnamed: 22'],
                    'Financial Information': ['Cost', 'Price', 'Refund', 'Exchange Price', 'Total', 'Tax', 'Restocking Fee', 'Shipping'],
                    'Return Information': ['Return Invoice', 'Return Date', 'Case Number', 'Name', 'Original Invoice', 'Original Date'],
                    'Additional Information': []
                }
                
                # تعيين الأعمدة المتبقية إلى الفئة الإضافية
                assigned_keys = set()
                for cat_keys in categories.values():
                    assigned_keys.update(cat_keys)
                
                for key in result.keys():
                    if key not in assigned_keys:
                        categories['Additional Information'].append(key)
                
                # عرض البيانات حسب الفئات
                for category, fields in categories.items():
                    if fields:
                        st.subheader(category)
                        
                        if category != 'Additional Information':
                            cols = st.columns(3)
                            for i, field in enumerate(fields):
                                if field in result:
                                    value = format_value(field, result[field])
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
                        else:
                            for field in fields:
                                if field in result:
                                    value = format_value(field, result[field])
                                    st.write(f"**{field}:** {value}")
                
                # رابط التتبع
                tracking_link = result.get('Link', '')
                if pd.notna(tracking_link) and tracking_link:
                    st.markdown(f"[Tracking Link]({tracking_link})")
        
        except Exception as e:
            logging.error(f"Search error: {e}")
            st.error(f'An error occurred: {e}')
            st.sidebar.text(traceback.format_exc())
            st.error('Please verify the IMEI number and data format')

# عرض البيانات الخام لتصحيح الأخطاء
if st.sidebar.checkbox("Show Raw Data"):
    st.sidebar.dataframe(df.head())
    
    if 'IMEI' in df.columns:
        st.sidebar.subheader("Sample IMEI values:")
        st.sidebar.write(df['IMEI'].head(10).tolist())
        
    st.sidebar.subheader("All available columns:")
    st.sidebar.write(df.columns.tolist())
