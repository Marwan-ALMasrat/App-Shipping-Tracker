def clean_imei(imei_value):
    """تنظيف قيمة IMEI مع الاحتفاظ بالأصفار البادئة."""
    try:
        # التحقق من أن القيمة ليست فارغة أو None
        if imei_value is None or pd.isna(imei_value):
            return ""
        
        # تحويل القيمة إلى سلسلة مباشرة
        imei_str = str(imei_value).strip()
        
        # إزالة '.0' فقط إذا كانت في نهاية السلسلة
        if imei_str.endswith('.0'):
            imei_str = imei_str[:-2]
        
        return imei_str
    except Exception as e:
        logging.error(f"Error cleaning IMEI {imei_value}: {e}")
        return ""

def load_data():
    """تحميل البيانات من ملف Excel."""
    try:
        timestamp = int(time.time())
        file_path = fetch_excel_file(timestamp)
        
        if not file_path or not os.path.exists(file_path):
            st.error("Could not download the Excel file.")
            return pd.DataFrame()
        
        df = pd.read_excel(file_path)
        
        # تنظيف الملف المؤقت
        try:
            os.unlink(file_path)
        except:
            logging.warning(f"Failed to delete temporary file: {file_path}")
        
        # إزالة الأعمدة غير الضرورية
        cols_to_drop = [col for col in df.columns if 'Unnamed: 34' in col or 'Unnamed: 0' in col or 'Dispute' in col]
        df = df.drop(cols_to_drop, axis=1, errors='ignore')
        
        # تنظيف عمود IMEI مع الاحتفاظ بالأصفار البادئة
        if 'IMEI' in df.columns:
            df['IMEI'] = df['IMEI'].apply(clean_imei)
        
        # عرض معلومات التتبع
        if not df.empty and 'IMEI' in df.columns:
            st.sidebar.text(f"Number of records: {len(df)}")
            st.sidebar.text(f"Sample IMEI: {df['IMEI'].iloc[0]}")
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
