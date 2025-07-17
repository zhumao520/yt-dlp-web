async def upload_file(self, file_path: str, **kwargs):
    """上传文件 - 增加数据库异常处理"""
    try:
        # 原有上传逻辑
        return await self._upload_file_impl(file_path, **kwargs)
        
    except sqlite3.ProgrammingError as e:
        if "closed database" in str(e):
            logger.warning("⚠️ Pyrogram 数据库已关闭，跳过此次操作")
            return None
        raise
    except Exception as e:
        logger.error(f"❌ 文件上传失败: {e}")
        raise