import re
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import pyautogui



def get_str_input(prompt, default_val, pattern) -> str:
    """
    单个PyAutoGUI弹窗实现：自动/高倍镜/低倍镜选择 + 放大倍数输入
    :return: 字典（type:类型, value:倍数），取消则返回None
    """
    # 弹窗提示文本（清晰说明操作规则）
    prompt_text = f"请选输入{prompt}"

    # 循环获取有效输入
    while True:
        # 核心弹窗：输入框+OK/Cancel按钮（模拟三个功能按钮+输入框）
        user_input = pyautogui.prompt(
            text=prompt_text,
            title=f"{prompt}设置",
            default=f"{default_val}"  # 默认自动模式
        )

        # 用户点击Cancel/关闭弹窗
        if user_input is None:
            pyautogui.alert(text=f"输入{prompt}不可被取消", title="提示")
            continue

        # 清理输入（去空格、转小写，兼容大小写输入）
        user_input = user_input.strip().lower()
        if not user_input:
            pyautogui.alert(text="输入不能为空！请按提示格式输入", title="输入错误")
            continue

        # ========== 解析输入内容 ==========
        if re.match(rf"{pattern}", user_input):
            # 自动转换为int/float
            return user_input
        else:
            error_mag = user_input
            pyautogui.alert(
                text=f"{prompt}'{error_mag}'不合法,需要满足正则{pattern}",
                title="输入错误"
            )
            continue


def get_number_input(prompt, default_val) -> float:
    """
    单个PyAutoGUI弹窗实现：自动/高倍镜/低倍镜选择 + 放大倍数输入
    :return: 字典（type:类型, value:倍数），取消则返回None
    """
    # 弹窗提示文本（清晰说明操作规则）
    prompt_text = f"请选输入{prompt}"

    # 循环获取有效输入
    while True:
        # 核心弹窗：输入框+OK/Cancel按钮（模拟三个功能按钮+输入框）
        user_input = pyautogui.prompt(
            text=prompt_text,
            title=f"{prompt}设置",
            default=f"{default_val}"  # 默认自动模式
        )

        # 用户点击Cancel/关闭弹窗
        if user_input is None:
            pyautogui.alert(text=f"输入{prompt}不可被取消", title="提示")
            continue

        # 清理输入（去空格、转小写，兼容大小写输入）
        user_input = user_input.strip().lower()
        if not user_input:
            pyautogui.alert(text="输入不能为空！请按提示格式输入", title="输入错误")
            continue

        # ========== 解析输入内容 ==========
        if re.match(r"^[0-9]+(\.[0-9]+)?$", user_input):
            # 自动转换为int/float
            magnification = float(user_input)
            return magnification
        else:
            error_mag = user_input
            pyautogui.alert(
                text=f"{prompt}'{error_mag}'不是合法数字！请输入整数/浮点数",
                title="输入错误"
            )
            continue


def on_submit():
    """点击开始执行按钮时的回调函数"""
    # 1. 获取各个组件中的用户输入值
    sample_name = entry_sample.get()
    mag_value = combo_mag.get()
    enable_drift = var_drift.get()  # True 或 False

    # 验证基础输入
    if not sample_name.strip():
        messagebox.showwarning("输入警告", "请输入样品名称！")
        return

    # 2. 弹出确认/取消对话框 (返回 True 或 False)
    message_text = f"请确认实验参数：\n\n" \
                   f"样品名称: {sample_name}\n" \
                   f"放大倍数: {mag_value}\n" \
                   f"开启漂移修正: {'是' if enable_drift else '否'}"

    is_confirmed = messagebox.askyesno("确认参数", message_text)

    # 3. 根据用户的选择执行后续逻辑
    if is_confirmed:
        print("用户点击了确定，开始执行自动化脚本...")
        # 在这里对接您的 AutoScript 核心逻辑
        label_status.config(text="状态：正在运行...", foreground="green")
    else:
        print("用户取消了操作。")
        label_status.config(text="状态：操作已取消", foreground="red")


if __name__ == '__main__':
    # ---- 主窗口初始化 ----
    root = tk.Tk()
    root.title("AutoScript 参数配置面板")
    root.geometry("400x280")  # 设置窗口宽高
    root.resizable(False, False)  # 禁止用户缩放窗口大小

    # 设置统一的内边距样式
    pad_opts = {'padx': 10, 'pady': 10}

    # ---- 1. 文本输入框 (Entry) ----
    label_sample = ttk.Label(root, text="样品名称:")
    label_sample.grid(row=0, column=0, sticky="w", **pad_opts)

    entry_sample = ttk.Entry(root, width=25)
    entry_sample.insert(0, "Sample_001")  # 设置默认文本
    entry_sample.grid(row=0, column=1, sticky="w", **pad_opts)

    # ---- 2. 下拉框 (Combobox) ----
    label_mag = ttk.Label(root, text="放大倍数:")
    label_mag.grid(row=1, column=0, sticky="w", **pad_opts)

    combo_mag = ttk.Combobox(root, width=23, state="readonly")  # readonly 表示不允许用户手动输入输入
    combo_mag['values'] = ("5000x", "10000x", "20000x", "50000x")  # 下拉菜单选项
    combo_mag.current(1)  # 默认选中第二个（10000x）
    combo_mag.grid(row=1, column=1, sticky="w", **pad_opts)

    # ---- 3. 复选/勾选框 (Checkbutton) ----
    label_drift = ttk.Label(root, text="漂移修正:")
    label_drift.grid(row=2, column=0, sticky="w", **pad_opts)

    var_drift = tk.BooleanVar(value=True)  # 定义一个布尔变量绑定勾选状态，默认True(勾选)
    check_drift = ttk.Checkbutton(root, text="启用 Drift Correction", variable=var_drift)
    check_drift.grid(row=2, column=1, sticky="w", **pad_opts)

    # ---- 4. 提交按钮 (Button) ----
    btn_submit = ttk.Button(root, text="开始执行任务", command=on_submit)  # command 绑定点击事件
    btn_submit.grid(row=3, column=0, columnspan=2, pady=20)

    # ---- 5. 状态状态栏 (可选) ----
    label_status = ttk.Label(root, text="状态：等待输入", font=("Arial", 10, "italic"))
    label_status.grid(row=4, column=0, columnspan=2, sticky="w", padx=10)

    # 启动窗口事件循环（让窗口一直保持显示）
    root.mainloop()

    print(f'Get input number: {get_number_input(prompt="放大倍数", default_val=1500)}')
