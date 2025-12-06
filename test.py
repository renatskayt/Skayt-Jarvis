import google.generativeai as genai
import subprocess
import os
import difflib

# ==========================================
#              НАСТРОЙКИ
# ==========================================

# ⚠️ ТВОЙ КЛЮЧ
GOOGLE_API_KEY = "AI_Key" 

# СЛЕНГ
ALIASES = {
    "телега": "telegram",
    "кс": "counter-strike",
    "дота": "dota 2",
    "пабг": "pubg",
    "браузер": "chrome",
    "хром": "chrome",
    "таппер": "tupperbox", 
    "дс": "discord",
    "калькулятор": "calc",
    "блокнот": "notepad"
}

# ИГНОР (Чтобы не искал проги на "привет")
IGNORE_WORDS = [
    "привет", "здравствуйте", "ку", "хай", "hello", "hi",
    "пока", "до свидания", "bb", "bye",
    "спасибо", "спс",
    "как дела", "что делаешь", "ты тут", "джарвис",
    "да", "нет", "ок", "хорошо", "ладно",
    "2+2", "сколько время", "который час", "кто ты",
    "создай папку", "выключи комп" # Добавил сюда команды, чтобы он не искал программу "создай папку"
]

TRIGGER_WORDS = ["открой", "запусти", "вруби", "покажи", "найди", "open", "start"]

genai.configure(api_key=GOOGLE_API_KEY)

# ==========================================
#           СИСТЕМНЫЕ ФУНКЦИИ
# ==========================================

def transliterate(text):
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    return "".join(mapping.get(char, char) for char in text.lower())

def get_programs_db():
    programs = {}
    search_paths = [
        os.path.join(os.environ["ProgramData"], "Microsoft", "Windows", "Start Menu"),
        os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu"),
        os.path.join(os.environ["USERPROFILE"], "Desktop"),
        os.path.join(os.environ["PUBLIC"], "Desktop")
    ]
    
    print(">> [SYSTEM]: Индексация программ...", end=" ")
    count = 0
    for path in search_paths:
        if not os.path.exists(path): continue
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith((".lnk", ".url", ".exe")):
                    name = file.lower().replace(".lnk", "").replace(".url", "").replace(".exe", "")
                    full_path = os.path.join(root, file)
                    programs[name] = full_path
                    count += 1
    print(f"Готово. Найдено {count} приложений.")
    return programs

APPS_DB = get_programs_db()
APPS_NAMES = list(APPS_DB.keys())

# ==========================================
#           ЛОГИКА ПОИСКА (TURBO)
# ==========================================

def fast_local_search(query: str):
    query_clean = query.lower().strip()
    
    # Anti-Fail: Если фраза в игноре или содержит слова "создай", "удали" -> пропускаем поиск программ
    if query_clean in IGNORE_WORDS or "создай" in query_clean or "выключи" in query_clean:
        return False, None

    has_trigger = False
    for word in TRIGGER_WORDS:
        if query_clean.startswith(word + " "):
            query_clean = query_clean.replace(word + " ", "", 1).strip()
            has_trigger = True
    
    if query_clean in ALIASES:
        query_clean = ALIASES[query_clean]

    translit_query = transliterate(query_clean)
    candidates = [query_clean, translit_query]
    best_match = None
    
    if query_clean in APPS_DB: best_match = query_clean
    elif translit_query in APPS_DB: best_match = translit_query
        
    if not best_match:
        cutoff_score = 0.6 if has_trigger else 0.85
        for cand in candidates:
            matches = difflib.get_close_matches(cand, APPS_NAMES, n=1, cutoff=cutoff_score)
            if matches:
                best_match = matches[0]
                break
    
    if not best_match and len(query_clean) > 3:
        for app in APPS_NAMES:
            if query_clean in app:
                best_match = app
                break

    if best_match:
        print(f">> [FAST LAUNCH]: Запускаю '{best_match}'")
        try:
            os.startfile(APPS_DB[best_match])
            return True, f"Запустил {best_match}"
        except Exception as e:
            return True, f"Ошибка запуска: {e}"
            
    return False, None

# ==========================================
#           ИИ МОЗГИ (GEMINI)
# ==========================================

def browser_search(query: str):
    """Гуглит информацию"""
    print(f">> [WEB]: Гуглю '{query}'")
    if "." in query and " " not in query:
        url = f"https://{query}"
    else:
        url = f"https://www.google.com/search?q={query}"
    subprocess.Popen(f"start {url}", shell=True)
    return f"Открыл браузер."

# --- НОВАЯ ФУНКЦИЯ: РУКИ ДЖАРВИСА ---
def execute_system_command(command: str):
    """
    Выполняет команды CMD Windows.
    Примеры:
    mkdir "folder" - создать папку
    shutdown /s /t 0 - выключить комп
    echo text > file.txt - создать файл
    """
    print(f">> [CMD]: Выполняю '{command}'")
    try:
        # shell=True позволяет выполнять команды консоли
        subprocess.run(command, shell=True, check=True)
        return "Команда выполнена успешно."
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"

# Добавляем новую функцию в инструменты
tools = [browser_search, execute_system_command]

model_name = "gemini-2.5-flash"

model = genai.GenerativeModel(
    model_name=model_name,
    tools=tools,
    system_instruction="""
    Ты Джарвис, ИИ с полным доступом к компьютеру (Windows).
    
    ТВОИ ИНСТРУМЕНТЫ:
    1. browser_search(query) -> Для поиска в интернете, открытия сайтов.
    2. execute_system_command(command) -> Для управления системой.
    
    ПРАВИЛА:
    - Если просят СОЗДАТЬ папку -> execute_system_command('mkdir "Название"')
    - Если просят ВЫКЛЮЧИТЬ компьютер -> execute_system_command('shutdown /s /t 0')
    - Если просят 2+2 или просто болтают -> ОТВЕЧАЙ ТЕКСТОМ.
    - Ты не можешь сносить системные файлы!!pyinstaller --onefile
    
    Веди себя уверенно.
    """
)
chat = model.start_chat(enable_automatic_function_calling=True)

# ==========================================
#           ГЛАВНЫЙ ЦИКЛ
# ==========================================

def main():
    print("=========================================")
    print(f"   J.A.R.V.I.S. (System Control Mode)")
    print("=========================================")
    
    while True:
        try:
            user_input = input("\n[Вы]: ").strip()
        except KeyboardInterrupt:
            break
            
        if not user_input or user_input.lower() in ["exit", "выход"]:
            break

        # 1. Сначала ищем программу
        found, msg = fast_local_search(user_input)
        if found:
            print(f"JARVIS: {msg}")
            continue 

        # 2. Если не программа — отдаем ИИ
        try:
            response = chat.send_message(user_input)
            
            if response.text:
                print(f"JARVIS: {response.text}")
            else:
                print(">> (Задача выполнена)")
                
        except Exception as e:
            print(f">> Ошибка: {e}")

if __name__ == "__main__":
    main()