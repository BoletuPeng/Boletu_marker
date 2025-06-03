#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

class QueryToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Query Tool")

        # --------------------------
        # 1. 定义默认路径/文件
        # --------------------------
        self.default_details_folder = "details"
        self.default_list_file = "list.txt"
        self.default_output_file = "output.txt"
        # 注意：此处硬编码了代码根文件夹，可以根据实际需求修改
        self.default_code_root_folder = r"C:\Users\Lenovo\OneDrive\桌面\project2025\my_perspective_app"

        # 这些是当前使用的路径/文件，初始值为默认值
        self.current_details_folder = self.default_details_folder
        self.current_list_file = self.default_list_file
        self.current_output_file = self.default_output_file
        self.current_code_root_folder = self.default_code_root_folder

        # --------------------------
        # 2. 主界面布局
        # --------------------------
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # ---- a) 各种路径设置区域 ----
        # 说明文件夹
        folder_details_layout = QHBoxLayout()
        self.details_folder_label = QLabel("说明文档文件夹:")
        self.details_folder_line = QLineEdit(self.current_details_folder)
        self.details_folder_btn = QPushButton("选择...")
        self.details_folder_btn.clicked.connect(self.on_select_details_folder)
        folder_details_layout.addWidget(self.details_folder_label)
        folder_details_layout.addWidget(self.details_folder_line)
        folder_details_layout.addWidget(self.details_folder_btn)
        layout.addLayout(folder_details_layout)

        # 代码根文件夹
        folder_code_layout = QHBoxLayout()
        self.code_folder_label = QLabel("代码根文件夹:")
        self.code_folder_line = QLineEdit(self.current_code_root_folder)
        self.code_folder_btn = QPushButton("选择...")
        self.code_folder_btn.clicked.connect(self.on_select_code_folder)
        folder_code_layout.addWidget(self.code_folder_label)
        folder_code_layout.addWidget(self.code_folder_line)
        folder_code_layout.addWidget(self.code_folder_btn)
        layout.addLayout(folder_code_layout)

        # 请求列表文件
        list_file_layout = QHBoxLayout()
        self.list_file_label = QLabel("请求列表文件:")
        self.list_file_line = QLineEdit(self.current_list_file)
        self.list_file_btn = QPushButton("选择...")
        self.list_file_btn.clicked.connect(self.on_select_list_file)
        list_file_layout.addWidget(self.list_file_label)
        list_file_layout.addWidget(self.list_file_line)
        list_file_layout.addWidget(self.list_file_btn)
        layout.addLayout(list_file_layout)

        # 输出文件
        output_file_layout = QHBoxLayout()
        self.output_file_label = QLabel("输出文件:")
        self.output_file_line = QLineEdit(self.current_output_file)
        self.output_file_btn = QPushButton("选择...")
        self.output_file_btn.clicked.connect(self.on_select_output_file)
        output_file_layout.addWidget(self.output_file_label)
        output_file_layout.addWidget(self.output_file_line)
        output_file_layout.addWidget(self.output_file_btn)
        layout.addLayout(output_file_layout)

        # ---- b) 执行按钮区域 ----
        buttons_layout = QHBoxLayout()

        self.button_descriptions = QPushButton("根据list.txt输出项目描述文件")
        self.button_descriptions.clicked.connect(self.on_generate_descriptions)
        buttons_layout.addWidget(self.button_descriptions)

        self.button_code = QPushButton("根据list.txt输出代码文件")
        self.button_code.clicked.connect(self.on_generate_code)
        buttons_layout.addWidget(self.button_code)

        layout.addLayout(buttons_layout)

        # 设置窗口大小
        self.resize(800, 300)

    # --------------------------
    # 3. 选择对话框事件回调
    # --------------------------
    def on_select_details_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择说明文档文件夹", self.current_details_folder)
        if folder:  # 用户确认了文件夹
            self.current_details_folder = folder
            self.details_folder_line.setText(folder)

    def on_select_code_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择代码根文件夹", self.current_code_root_folder)
        if folder:
            self.current_code_root_folder = folder
            self.code_folder_line.setText(folder)

    def on_select_list_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择请求列表文件", self.current_list_file, "Text Files (*.txt);;All Files (*)")
        if file_name:
            self.current_list_file = file_name
            self.list_file_line.setText(file_name)

    def on_select_output_file(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "选择输出文件", self.current_output_file, "Text Files (*.txt);;All Files (*)")
        if file_name:
            self.current_output_file = file_name
            self.output_file_line.setText(file_name)

    # --------------------------
    # 4. 核心功能：生成描述文件
    # --------------------------
    def on_generate_descriptions(self):
        """
        根据list.txt输出项目描述文件（与之前的脚本逻辑类似）。
        """
        details_folder = self.details_folder_line.text()
        list_file = self.list_file_line.text()
        output_file = self.output_file_line.text()

        # 1) 检查list_file是否存在
        if not os.path.exists(list_file):
            QMessageBox.critical(self, "错误", f"未找到请求列表文件: {list_file}")
            return

        # 读取请求列表
        with open(list_file, "r", encoding="utf-8") as f:
            requested_files = [line.strip() for line in f if line.strip()]

        if not requested_files:
            QMessageBox.information(self, "提示", f"{list_file} 中没有要查询的文件名，结束。")
            return

        # 2) 如果输出文件已存在，则先删除
        if os.path.exists(output_file):
            os.remove(output_file)

        missing_files = []

        with open(output_file, "w", encoding="utf-8") as out_f:
            for file_name in requested_files:
                txt_filename = f"{file_name}.txt"
                details_path = os.path.join(details_folder, txt_filename)

                if os.path.exists(details_path):
                    with open(details_path, "r", encoding="utf-8") as in_f:
                        content = in_f.read()

                    out_f.write(f"## {file_name}:\n\n")
                    out_f.write(content)
                    out_f.write("\n\n")
                else:
                    missing_files.append(file_name)

            # 写出未找到的文件信息
            if missing_files:
                out_f.write("没有找到以下文件的详细说明文档(可能名称错误或不存在)：\n")
                out_f.write(", ".join(missing_files))
                out_f.write("\n")

        QMessageBox.information(self, "完成", f"查询完成！结果已写入 {output_file}。\n\n"
                                             f"未找到: {', '.join(missing_files) if missing_files else '无'}")

    # --------------------------
    # 5. 核心功能：生成代码文件
    # --------------------------
    def on_generate_code(self):
        """
        根据list.txt输出代码文件。
        会对 self.current_code_root_folder 进行递归搜索，找到与list中名称对应的 .py 文件并拼接输出。
        """
        code_root_folder = self.code_folder_line.text()
        list_file = self.list_file_line.text()
        output_file = self.output_file_line.text()

        # 1) 检查list_file是否存在
        if not os.path.exists(list_file):
            QMessageBox.critical(self, "错误", f"未找到请求列表文件: {list_file}")
            return

        # 读取请求列表
        with open(list_file, "r", encoding="utf-8") as f:
            requested_files = [line.strip() for line in f if line.strip()]

        if not requested_files:
            QMessageBox.information(self, "提示", f"{list_file} 中没有要查询的文件名，结束。")
            return

        # 2) 如果输出文件已存在，则先删除
        if os.path.exists(output_file):
            os.remove(output_file)

        missing_files = []

        with open(output_file, "w", encoding="utf-8") as out_f:
            for file_name in requested_files:
                # 这里假设list里写的是 "xxx_controller.py"
                # 需要在 code_root_folder 中递归搜索这个文件
                found_path = self.find_file_recursively(code_root_folder, file_name)
                if found_path:
                    with open(found_path, "r", encoding="utf-8") as code_f:
                        code_content = code_f.read()

                    out_f.write(f"\n\n{file_name} 代码文件内容如下：\n\n")
                    out_f.write(code_content)
                    out_f.write("\n\n")
                else:
                    missing_files.append(file_name)

            # 写出未找到的文件信息
            if missing_files:
                out_f.write("没有找到以下代码文件(可能名称错误或不存在)：\n")
                out_f.write(", ".join(missing_files))
                out_f.write("\n")

        QMessageBox.information(self, "完成", f"查询完成！结果已写入 {output_file}。\n\n"
                                             f"未找到: {', '.join(missing_files) if missing_files else '无'}")

    # --------------------------
    # 6. 辅助函数：递归搜索文件
    # --------------------------
    def find_file_recursively(self, root_folder, target_filename):
        """
        在给定的root_folder下递归搜索target_filename，找到则返回完整路径，否则返回None
        """
        for root, dirs, files in os.walk(root_folder):
            if target_filename in files:
                return os.path.join(root, target_filename)
        return None


def main():
    app = QApplication(sys.argv)
    window = QueryToolWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
