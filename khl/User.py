class User:
    """
    presents a User in chat/group

    including other bots
    """

    def __init__(self, data):
        self.id = data['id']
        self.nickname = data['nickname']
        pass
