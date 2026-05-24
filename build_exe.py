import os
import subprocess
import sys

def build():
    print("--- 開始打包 神控無限簡報筆系統 ---")
    
    # 定義隔離的虛擬環境目錄
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv_build")
    
    # 判斷作業系統以決定執行檔路徑
    is_windows = os.name == 'nt'
    if is_windows:
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
        pyinstaller_exe = os.path.join(venv_dir, "Scripts", "pyinstaller.exe")
        sep = ';'
    else:
        python_exe = os.path.join(venv_dir, "bin", "python")
        pip_exe = os.path.join(venv_dir, "bin", "pip")
        pyinstaller_exe = os.path.join(venv_dir, "bin", "pyinstaller")
        sep = ':'
        
    # 1. 建立虛擬環境
    if not os.path.exists(venv_dir):
        print(f"正在建立隔離的虛擬環境: {venv_dir} ...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        print("虛擬環境建立成功！")
    else:
        print("已偵測到現有的虛擬環境，將直接使用以加快速度。")
        
    # 2. 在虛擬環境中安裝核心依賴
    print("正在虛擬環境中安裝必要依賴 (eel, bottle, bottle-websocket, pyinstaller, pyautogui, pillow, pyperclip)...")
    # 先升級 pip 確保安全與正確性
    subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([
        pip_exe, "install", 
        "eel", "bottle", "bottle-websocket", "pyinstaller", "pyautogui", "pillow", "pyperclip"
    ])
    print("依賴安裝完成！")

    # 3. 執行 PyInstaller 打包
    exe_name = "shen-remote-presenter"
    
    cmd = [
        pyinstaller_exe,
        "--onefile",
        "--noconsole",
        "--clean",
        f"--add-data=web{sep}web",
        "--hidden-import=bottle_websocket",
        f"--name={exe_name}",
        "main.py"
    ]
    
    print(f"執行 PyInstaller 打包指令: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print(f"\n--- 打包完成！ ---")
        
        # 顯示 EXE 檔案大小
        dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
        exe_path = os.path.join(dist_dir, f"{exe_name}.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"打包產出檔案: {exe_path}")
            print(f"檔案大小: {size_mb:.2f} MB")
            if size_mb < 98:
                print("成功！檔案大小已低於 98MB！")
            else:
                print("警告：檔案大小仍大於 98MB。")
        else:
            print("找不到產出的執行檔，請檢查錯誤日誌。")
            
    except subprocess.CalledProcessError as e:
        print(f"\n打包失敗: {e}")

if __name__ == "__main__":
    build()
