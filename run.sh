
VENV_DIR=".venv"
REQUIREMENTS_FILE="requirements.txt"
MAIN_FILE="main.py"

if [ ! -d "$VENV_DIR" ]; then
    echo "Створюється віртуальне середовище..."
    python3 -m venv "$VENV_DIR" || { echo "Не вдалося створити venv"; exit 1; }
else
    echo "Віртуальне середовище вже існує."
fi

echo "Активується venv..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate" || { echo "Не вдалося активувати venv"; exit 1; }

if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Перевіряємо встановлені пакети..."
    MISSING=$(pip freeze | grep -Fxf "$REQUIREMENTS_FILE" | wc -l)
    TOTAL=$(cat "$REQUIREMENTS_FILE" | grep -vc '^#')

    if [ "$MISSING" -lt "$TOTAL" ]; then
        echo "Встановлюються залежності з $REQUIREMENTS_FILE..."
        pip install -r "$REQUIREMENTS_FILE" || { echo "Помилка при встановленні залежностей"; exit 1; }
    else
        echo "Усі залежності вже встановлені."
    fi
else
    echo "Файл $REQUIREMENTS_FILE не знайдено!"
    exit 1
fi

if [ -f "$MAIN_FILE" ]; then
    echo "Запускається $MAIN_FILE..."
    python tasks.py run "$@"
else
    echo "Файл $MAIN_FILE не знайдено!"
    exit 1
fi
