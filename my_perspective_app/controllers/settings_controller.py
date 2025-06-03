# my_perspective_app/controllers/settings_controller.py

import os

class SettingsController:
    """
    用于管理 settings.txt 的读取与写入。
    在这里我们可扩展更多配置项，目前只示例 canvas_height。
    """

    def __init__(self, settings_path):
        """
        :param settings_path: 本地 settings.txt 的文件路径(与 main.py 同目录)
        """
        self.settings_path = settings_path

        # 缓存配置的字段。例如：{"canvas_height": 1000}
        self.config_data = {
            "canvas_height": 1000
        }

        # 初始化时，若文件不存在则自动创建一个默认文件
        if not os.path.exists(self.settings_path):
            self._write_to_file()
        # 如果已存在，则读入
        else:
            self.load_from_file(self.settings_path)

    def load_from_file(self, path):
        """
        从指定 path 读取配置，并将其写入 self.config_data 中。
        仅处理“canvas_height=xxx”这种简单形式，后续可扩展。
        """
        if not os.path.exists(path):
            return  # 不做任何处理
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('canvas_height='):
                    val_str = line.split('=', 1)[1]
                    try:
                        val = int(val_str)
                        # clamp到允许范围 [500,4000]
                        val = max(500, min(val, 4000))
                        self.config_data["canvas_height"] = val
                    except ValueError:
                        pass

    def overwrite_local_settings_with(self, external_path):
        """
        读取外部的配置文件 external_path，写入到 self.config_data 后，
        再将结果保存到 self.settings_path（覆盖本地 settings.txt）。
        """
        if os.path.exists(external_path):
            self.load_from_file(external_path)
            self._write_to_file()

    def _write_to_file(self):
        """
        将 self.config_data 写回 self.settings_path
        """
        with open(self.settings_path, 'w', encoding='utf-8') as f:
            # 只写这一个字段示例
            f.write(f"canvas_height={self.config_data['canvas_height']}\n")

    # =============================
    #  以下提供对外访问的 getter/setter
    # =============================
    def get_canvas_height(self):
        return self.config_data.get("canvas_height", 1000)

    def set_canvas_height(self, new_height):
        new_height = max(500, min(new_height, 4000))
        self.config_data["canvas_height"] = new_height
        self._write_to_file()

