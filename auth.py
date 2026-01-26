import database

def login_user(username, password):
    """
    ユーザー名とパスワードを検証してログインする
    """
    # ユーザー情報を取得（辞書形式で返ってきます）
    user = database.get_user_by_username(username)
    
    if user is None:
        return None
        
    # パスワードの照合
    # 以前は user[2] でしたが、今は user['password'] で指定します
    if user['password'] == password:
        return user
        
    return None