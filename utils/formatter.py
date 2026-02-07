import os

def format_folder_name(platform_raw, user_name):
    """
    Mengubah input jadi format Industrial ART'TERYX.
    Input: tiktok, billaazz
    Output: TIKTOK | BILLAAZZ (Hanya string nama untuk Telegram Topic)
    """
    # 1. Standarisasi Input
    if not platform_raw: platform_raw = "GENERAL"
    if not user_name: user_name = "USER"
    
    # 2. Bersihkan dan buat jadi UPPERCASE (Industrial Style)
    platform = platform_raw.strip().upper()
    user = user_name.strip().upper()

    # 3. Formatting Nama untuk Topic Telegram
    # Hasil: TIKTOK | BILLAAZZ (Gak pake emote, gak pake path downloads/)
    folder_name_string = f"{platform} | {user}"
    
    # 4. KEMBALIKAN HANYA NAMA STRING
    # Jangan buat folder os.makedirs di sini lagi, biar diatur sama app.py 
    # supaya gak terjadi duplikasi folder nyasar.
    return folder_name_string
