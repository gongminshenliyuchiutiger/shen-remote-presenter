import eel
import os
import sys
import socket
import io
import base64
import pyautogui
from PIL import Image
from datetime import datetime
import ctypes
import threading
import time
import math

# 設定 PyAutoGUI 以獲得最高流暢度
pyautogui.FAILSAFE = True  # 移到角落可中斷
pyautogui.PAUSE = 0.0      # 移動間不留延遲

if hasattr(sys, '_MEIPASS'):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

web_dir = os.path.join(base_dir, 'web')

# 系統狀態與操作日誌
state = {
    "server_ip": "",
    "client_connected": False,
    "logs": []  # 儲存結構為 {time: "HH:MM:SS", action: "說明"}
}

# 心跳包監控變數與線程鎖，用於主動離線偵測
last_heartbeat_time = 0.0
heartbeat_lock = threading.Lock()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 連接一個外部 IP (不會真的發送封包，只為獲取本機對外 IP)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

state["server_ip"] = get_local_ip()

def add_log(action_text):
    """新增一筆操作記錄並同步更新電腦端 UI"""
    now = datetime.now().strftime("%H:%M:%S")
    state["logs"].append({
        "time": now,
        "action": action_text
    })
    # 限制日誌最大筆數，防止記憶體膨脹
    if len(state["logs"]) > 50:
        state["logs"] = state["logs"][-50:]
    eel.update_ui(state)

# --- 暴露給手機端與電腦端的前端函式 ---

@eel.expose
def get_system_status():
    """獲取當前系統狀態"""
    return state

@eel.expose
def client_connect(device_info="行動裝置"):
    """當行動裝置載入頁面連線時呼叫"""
    global last_heartbeat_time
    with heartbeat_lock:
        state["client_connected"] = True
        last_heartbeat_time = time.time()
    add_log(f"遠端連線成功：{device_info}")
    return True

@eel.expose
def client_ping():
    """行動裝置心跳包，維持連線狀態"""
    global last_heartbeat_time
    with heartbeat_lock:
        state["client_connected"] = True
        last_heartbeat_time = time.time()
    return True

# Windows 虛擬鍵碼映射表，提供原生、高效且穩定的鍵盤模擬，繞過 PyAutoGUI 修飾鍵限制
VK_CODES = {
    'ctrl': 0x11,
    'ctrlleft': 0x11,
    'ctrlright': 0xA3,
    'alt': 0x12,
    'altleft': 0x12,
    'altright': 0xA5,
    'shift': 0x10,
    'shiftleft': 0xA0,
    'shiftright': 0xA1,
    'win': 0x5B,
    'winleft': 0x5B,
    'winright': 0x5C,
    'up': 0x26,
    'down': 0x28,
    'left': 0x25,
    'right': 0x27,
    'backspace': 0x08,
    'delete': 0x2E,
    'enter': 0x0D,
    'tab': 0x09,
    'space': 0x20,
    'home': 0x24,
    'end': 0x23,
    'pageup': 0x21,
    'pagedown': 0x22,
    'volumedown': 0xAE,
    'volumeup': 0xAF,
    'volumemute': 0xAD,
    'f4': 0x73,
    'f5': 0x74,
    'escape': 0x1B,
    'esc': 0x1B,
}

@eel.expose
def remote_key_press(key, name="按鍵"):
    """模擬鍵盤按鍵"""
    try:
        key_lower = key.lower()
        
        # 在 Windows 平台下，優先使用原生 keybd_event API，以防 PyAutoGUI 對修飾鍵（如 Win 鍵）的時序與權限失效
        if sys.platform == 'win32':
            parts = key_lower.split('+')
            vk_list = []
            for p in parts:
                p_clean = p.strip()
                if p_clean in VK_CODES:
                    vk_list.append(VK_CODES[p_clean])
                elif len(p_clean) == 1:
                    # 動態查詢 Windows 下的虛擬鍵碼 (VkKeyScanW)
                    vk = ctypes.windll.user32.VkKeyScanW(ord(p_clean)) & 0xFF
                    if vk != 0xFF:
                        vk_list.append(vk)
                    else:
                        vk_list.append(ord(p_clean.upper()))
                else:
                    raise ValueError(f"無法識別的按鍵：{p_clean}")
            
            # 模擬按鍵：順序按下
            for vk in vk_list:
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            # 模擬放開：逆序釋放
            for vk in reversed(vk_list):
                ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0) # 0x0002 代表 KEYEVENTF_KEYUP
                
            add_log(f"鍵盤指令 (原生)：{name} ({key})")
            return True
            
        else:
            # 非 Windows 平台，降級使用 PyAutoGUI 進行模擬
            if '+' in key_lower:
                parts = key_lower.split('+')
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(key_lower)
            add_log(f"鍵盤指令 (PyAutoGUI)：{name} ({key})")
            return True
            
    except Exception as e:
        add_log(f"鍵盤指令失敗：{str(e)}")
        return False

@eel.expose
def remote_mouse_move(dx, dy, sensitivity=1.0):
    """模擬滑鼠相對移動"""
    try:
        mx = int(dx * sensitivity)
        my = int(dy * sensitivity)
        if sys.platform == 'win32':
            # 獲取當前滑鼠位置並計算新位置，透過 win32 絕對定位事件發送，以確保拖曳畫線能被正確偵測
            x, y = pyautogui.position()
            win32_move_to_absolute(x + mx, y + my)
        else:
            # 使用 _pause=False 參數能使移動更為平滑且無卡頓
            pyautogui.moveRel(mx, my, _pause=False)
        return True
    except Exception:
        return False

def win32_move_to_absolute(x, y):
    """在 Windows 系統下，使用 mouse_event 模擬絕對滑鼠移動。
    這樣能將事件發送至系統硬體輸入佇列，確保小畫家、PowerPoint 等繪圖程式能正確識別滑鼠拖曳與畫線軌跡。
    """
    try:
        # 獲取系統指標解析度（能正確處理 DPI 縮放）
        sys_w = ctypes.windll.user32.GetSystemMetrics(0)
        sys_h = ctypes.windll.user32.GetSystemMetrics(1)
        # 轉換為 Windows mouse_event 絕對座標範圍 (0 ~ 65535)
        cx = int(65536 * x / sys_w) + 1
        cy = int(65536 * y / sys_h) + 1
        # MOUSEEVENTF_MOVE = 0x0001
        # MOUSEEVENTF_ABSOLUTE = 0x8000
        ctypes.windll.user32.mouse_event(0x0001 | 0x8000, cx, cy, 0, 0)
        return True
    except Exception:
        return False

@eel.expose
def remote_mouse_move_absolute(px, py):
    """模擬滑鼠絕對移動 (px, py 為行動端傳回的 0.0 ~ 1.0 比例值，用於畫線與指引)"""
    try:
        # 進行 NaN 與空值安全防護，防止圖片加載失敗時前端座標計算異常導致後端崩潰
        if math.isnan(px) or math.isnan(py):
            return False
            
        screenWidth, screenHeight = pyautogui.size()
        x = int(px * screenWidth)
        y = int(py * screenHeight)
        
        # 邊界限制安全防護
        x = max(0, min(x, screenWidth - 1))
        y = max(0, min(y, screenHeight - 1))
        
        # 絕對定位移動
        if sys.platform == 'win32':
            win32_move_to_absolute(x, y)
        else:
            pyautogui.moveTo(x, y, _pause=False)
        return True
    except Exception:
        return False

@eel.expose
def remote_mouse_down_absolute(px, py):
    """模擬滑鼠移至絕對比例位置並按住左鍵 (用於直接在大螢幕上畫圖/點按)"""
    try:
        if math.isnan(px) or math.isnan(py):
            return False
            
        screenWidth, screenHeight = pyautogui.size()
        x = int(px * screenWidth)
        y = int(py * screenHeight)
        x = max(0, min(x, screenWidth - 1))
        y = max(0, min(y, screenHeight - 1))
        
        # 移動並按住左鍵
        if sys.platform == 'win32':
            win32_move_to_absolute(x, y)
        else:
            pyautogui.moveTo(x, y, _pause=False)
        pyautogui.mouseDown(button='left')
        return True
    except Exception:
        return False

@eel.expose
def remote_mouse_up_absolute():
    """模擬滑鼠左鍵放開"""
    try:
        pyautogui.mouseUp(button='left')
        return True
    except Exception:
        return False

@eel.expose
def remote_mouse_down(button):
    """模擬滑鼠按鍵按住 (左鍵或右鍵)"""
    try:
        pyautogui.mouseDown(button=button)
        return True
    except Exception:
        return False

@eel.expose
def remote_mouse_up(button):
    """模擬滑鼠按鍵放開 (左鍵或右鍵)"""
    try:
        pyautogui.mouseUp(button=button)
        return True
    except Exception:
        return False

@eel.expose
def remote_mouse_click(button):
    """模擬滑鼠點擊"""
    try:
        if button == 'left':
            pyautogui.click(button='left')
            add_log("滑鼠動作：左鍵點擊")
        elif button == 'right':
            pyautogui.click(button='right')
            add_log("滑鼠動作：右鍵點擊")
        elif button == 'double':
            pyautogui.doubleClick()
            add_log("滑鼠動作：雙擊左鍵")
        return True
    except Exception as e:
        add_log(f"滑鼠點擊失敗：{str(e)}")
        return False

@eel.expose
def remote_mouse_scroll(clicks):
    """模擬滑鼠滾輪滾動 (clicks 正為向上，負為向下)"""
    try:
        # 乘以 50 放大滾動距離以符合操作習慣
        pyautogui.scroll(int(clicks * 50))
        return True
    except Exception:
        return False

@eel.expose
def remote_type_text(text, press_enter=False):
    """模擬鍵盤輸入文字 (支援中英文及特殊字元)"""
    try:
        import pyperclip
        import time
        
        # 增加剪貼簿寫入重試機制，防止 Windows 系統剪貼簿被其他背景服務暫時鎖定時報錯
        success_copied = False
        for i in range(5):
            try:
                pyperclip.copy(text)
                success_copied = True
                break
            except Exception:
                time.sleep(0.05)
                
        if not success_copied:
            raise RuntimeError("系統剪貼簿遭鎖定，無法寫入文字。")
            
        pyautogui.hotkey('ctrl', 'v')
        
        log_msg = f"文字輸入：傳送「{text}」"
        if press_enter:
            pyautogui.press('enter')
            log_msg += " 並按下 Enter"
        
        add_log(log_msg)
        return True
    except Exception as e:
        add_log(f"文字輸入失敗：{str(e)}")
        return False

last_active_hwnd = None

@eel.expose
def cycle_window_state():
    """在 Windows 系統下，對當前作用中視窗進行『最大化 -> 還原 -> 最小化 -> 最大化』循環切換 (鎖定同一個視窗)"""
    global last_active_hwnd
    try:
        if sys.platform != 'win32':
            # 非 Windows 平台使用熱鍵退回
            pyautogui.hotkey('win', 'up')
            return True
        
        import ctypes
        
        # 定義 WINDOWPLACEMENT 結構
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)
            ]
            
        class WINDOWPLACEMENT(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_uint),
                ("flags", ctypes.c_uint),
                ("showCmd", ctypes.c_uint),
                ("ptMinPosition", POINT),
                ("ptMaxPosition", POINT),
                ("rcNormalPosition", RECT)
            ]
        
        # 獲取當前最上層視窗
        current_foreground = ctypes.windll.user32.GetForegroundWindow()
        
        # 決定我們要操作的 target_hwnd
        target_hwnd = None
        
        # 檢查 last_active_hwnd 是否仍存在且有效
        is_last_valid = False
        if last_active_hwnd:
            is_last_valid = ctypes.windll.user32.IsWindow(last_active_hwnd) != 0
            
        if is_last_valid:
            # 取得 last_active_hwnd 的當前狀態
            placement = WINDOWPLACEMENT()
            placement.length = ctypes.sizeof(WINDOWPLACEMENT)
            ctypes.windll.user32.GetWindowPlacement(last_active_hwnd, ctypes.byref(placement))
            # 狀態 2 代表最小化 (SW_SHOWMINIMIZED / SW_MINIMIZE)
            is_minimized = (placement.showCmd == 2)
            
            # 如果目前作用中視窗就是上一次的，或是上一次操作的視窗正處於最小化狀態，我們就繼續使用同一個視窗
            if current_foreground == last_active_hwnd or is_minimized:
                target_hwnd = last_active_hwnd
            else:
                # 否則，表示使用者在電腦上點選了新視窗，我們更新鎖定目標
                target_hwnd = current_foreground
                last_active_hwnd = current_foreground
        else:
            target_hwnd = current_foreground
            last_active_hwnd = current_foreground
            
        if not target_hwnd:
            return False
            
        placement = WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(WINDOWPLACEMENT)
        
        if ctypes.windll.user32.GetWindowPlacement(target_hwnd, ctypes.byref(placement)):
            show_cmd = placement.showCmd
            # showCmd 常數:
            # SW_SHOWNORMAL = 1 (還原/正常)
            # SW_SHOWMINIMIZED = 2 (最小化)
            # SW_SHOWMAXIMIZED = 3 (最大化)
            
            if show_cmd == 3: # 當前為最大化，切換為還原
                ctypes.windll.user32.ShowWindow(target_hwnd, 9) # 9 = SW_RESTORE
                add_log("視窗控制：視窗還原")
            elif show_cmd == 1: # 當前為還原，切換為最小化
                ctypes.windll.user32.ShowWindow(target_hwnd, 6) # 6 = SW_MINIMIZE / SW_SHOWMINIMIZED
                add_log("視窗控制：視窗最小化")
            else: # 當前為最小化或其他，切換為最大化
                ctypes.windll.user32.ShowWindow(target_hwnd, 3) # 3 = SW_SHOWMAXIMIZED
                # 將視窗重新帶回最上層並啟用
                ctypes.windll.user32.SetForegroundWindow(target_hwnd)
                add_log("視窗控制：視窗最大化")
            return True
    except Exception as e:
        add_log(f"視窗控制切換失敗：{str(e)}")
        return False

@eel.expose
def get_screenshot():
    """擷取當前主螢幕畫面 (不限制寬度，維持與電腦直接截圖一樣清楚的原始解析度)"""
    try:
        img = pyautogui.screenshot()
        buffered = io.BytesIO()
        
        # 以 JPEG 格式儲存並壓縮畫質為 85% 以獲得極致清晰與檔案體積的最佳平衡
        img.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return {
            "status": "success", 
            "image": "data:image/jpeg;base64," + img_str
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@eel.expose
def clear_logs():
    """清除操作日誌"""
    state["logs"] = []
    eel.update_ui(state)
    return True

def monitor_heartbeat():
    """背景執行緒：定期檢查手機心跳包是否超時。若超時，將連線狀態自動設為離線。"""
    global last_heartbeat_time
    while True:
        time.sleep(2.0)
        with heartbeat_lock:
            if state["client_connected"]:
                # 如果超過 8 秒沒有收到心跳包，判定為離線
                if time.time() - last_heartbeat_time > 8.0:
                    state["client_connected"] = False
                    # 新增離線日誌
                    now = datetime.now().strftime("%H:%M:%S")
                    state["logs"].append({
                        "time": now,
                        "action": "遠端裝置已中斷連線 (連線超時)"
                    })
                    if len(state["logs"]) > 50:
                        state["logs"] = state["logs"][-50:]
                    try:
                        eel.update_ui(state)
                    except Exception:
                        pass

def handle_close(page, sockets):
    """當頁面關閉時的回呼函式。若電腦端主視窗關閉，則強制結束整個程式。"""
    if 'index.html' in page:
        print("電腦端主畫面已關閉，正在結束程式...")
        import os
        os._exit(0)

def main():
    eel.init(web_dir)
    
    # 啟動心跳監控背景執行緒
    t = threading.Thread(target=monitor_heartbeat, daemon=True)
    t.start()
    
    ip = get_local_ip()
    state["server_ip"] = ip
    port = 8000
    print(f"神控無限簡報筆系統啟動中...")
    print(f"電腦接收端網址: http://{ip}:{port}")
    
    try:
        # 啟動 Eel 應用程式。主畫面為 index.html (電腦端)
        # 手機控制端網址將是 http://<ip>:<port>/remote.html
        eel.start('index.html', size=(1000, 750), host=ip, port=port, close_callback=handle_close)
    except (SystemExit, KeyboardInterrupt):
        print("系統關閉中...")

if __name__ == "__main__":
    main()
