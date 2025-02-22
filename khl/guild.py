from os import remove
from typing import List, Dict, Union
from PIL import Image

from . import api
from .channel import Channel, public_channel_factory
from .gateway import Requestable
from .interface import LazyLoadable, ChannelTypes, GuildMuteTypes, InviteDurationTypes, InviteSettingTimesTypes
from .role import Role
from .user import User


class Guild(LazyLoadable, Requestable):
    """
    `Standard Object`

    represent a server where users gathered in and contains channels
    """
    id: str
    name: str
    topic: str
    master_id: str
    icon: str
    notify_type: int
    region: str
    enable_open: bool
    open_id: str
    default_channel_id: str
    welcome_channel_id: str
    _roles: List[Role]
    _channel_categories: List[Dict]
    _channels: List[Channel]

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self._channel_categories = []
        self._loaded = kwargs.get('_lazy_loaded_', False)
        self.gate = kwargs.get('_gate_', None)
        self._update_fields(**kwargs)

    def _update_fields(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.topic = kwargs.get('topic', '')
        self.master_id = kwargs.get('master_id', '')
        self.icon = kwargs.get('icon', '')
        self.notify_type = kwargs.get('notify_type', 0)
        self.region = kwargs.get('region', '')
        self.enable_open = kwargs.get('enable_open', False)
        self.open_id = kwargs.get('open_id', '')
        self.default_channel_id = kwargs.get('default_channel_id', '')
        self.welcome_channel_id = kwargs.get('welcome_channel_id', '')
        self._roles = kwargs.get('roles', None)
        self._channels = kwargs.get('channels', None)

    async def load(self):
        self._update_fields(**(await self.gate.exec_req(api.Guild.view(self.id))))
        self._loaded = True

    async def fetch_channel_list(self, force_update: bool = True) -> List[Channel]:
        if force_update or self._channels is None:
            raw_list = await self.gate.exec_pagination_req(api.Channel.list(guild_id=self.id))
            channel_list: List[Channel] = []
            for i in raw_list:
                if i['type'] == ChannelTypes.CATEGORY:
                    self._channel_categories.append(i)
                else:
                    channel_list.append(public_channel_factory(_gate_=self.gate, **i))
            self._channels = channel_list
        return self._channels

    @property
    def channels(self) -> List[Channel]:
        """
        get guild's channel list

        RECOMMEND: use ``await fetch_channel_list()``

        CAUTION: please call ``await fetch_me()`` first to load data from khl server

        designed as 'empty-then-fetch' will break the rule 'net-related is async'
        """
        if self._channels is not None:
            return self._channels
        raise ValueError('not loaded, please call `await fetch_channel_list()` first')

    async def list_user(self, channel: Channel) -> List[User]:
        users = await self.gate.exec_pagination_req(api.Guild.userList(guild_id=self.id, channel_id=channel.id))
        return [User(_gate_=self.gate, _lazy_loaded_=True, **i) for i in users]

    async def fetch_user(self, user_id: str) -> User:
        """get user object from user_id, can only fetch user in current guild
        """
        user = await self.gate.exec_req(api.User.view(user_id=user_id, guild_id=self.id))
        return User(_gate_=self.gate, _lazy_loaded_=True, **user)

    async def set_user_nickname(self, user: User, new_nickname: str):
        await self.gate.exec_req(api.Guild.nickname(guild_id=self.id, nickname=new_nickname, user_id=user.id))

    async def fetch_roles(self, force_update: bool = True) -> List[Role]:
        if force_update or self._roles is None:
            raw_list = await self.gate.exec_pagination_req(api.GuildRole.list(guild_id=self.id))
            self._roles = [Role(**i) for i in raw_list]
        return self._roles

    async def create_role(self, role_name: str) -> Role:
        return Role(**(await self.gate.exec_req(api.GuildRole.create(guild_id=self.id, name=role_name))))

    async def update_role(self, new_role: Role) -> Role:
        return Role(**(await self.gate.exec_req(api.GuildRole.update(guild_id=self.id, **vars(new_role)))))

    async def delete_role(self, role_id: int):
        return await self.gate.exec_req(api.GuildRole.delete(guild_id=self.id, role_id=role_id))

    async def grant_role(self, user: User, role: Union[Role, str]):
        """
        docs:
        https://developer.kaiheila.cn/doc/http/guild-role#%E8%B5%8B%E4%BA%88%E7%94%A8%E6%88%B7%E8%A7%92%E8%89%B2
        """
        role_id = role.id if isinstance(role, Role) else role
        return await self.gate.exec_req(api.GuildRole.grant(guild_id=self.id, user_id=user.id, role_id=role_id))

    async def revoke_role(self, user: User, role: Union[Role, str]):
        """
        docs:
        https://developer.kaiheila.cn/doc/http/guild-role#%E5%88%A0%E9%99%A4%E7%94%A8%E6%88%B7%E8%A7%92%E8%89%B2
        """
        role_id = role.id if isinstance(role, Role) else role
        return await self.gate.exec_req(api.GuildRole.revoke(guild_id=self.id, user_id=user.id, role_id=role_id))

    async def create_channel(self,
                             name: str,
                             type: ChannelTypes = None,
                             category: str = None,
                             limit_amount: int = None,
                             voice_quality: int = None):
        """docs: https://developer.kaiheila.cn/doc/http/channel#%E5%88%9B%E5%BB%BA%E9%A2%91%E9%81%93"""
        params = {'name': name, 'guild_id': self.id}
        if type:
            params['type'] = type.value
        if category:
            params['parent_id'] = category
        if limit_amount:
            params['limit_amount'] = limit_amount
        if voice_quality:
            params['voice_quality'] = voice_quality
        return public_channel_factory(self.gate, **(await self.gate.exec_req(api.Channel.create(**params))))

    async def kickout(self, user: Union[User, str]):
        target_id = user.id if isinstance(user, User) else user
        return await self.gate.exec_req(api.Guild.kickout(guild_id=self.id, target_id=target_id))

    async def leave(self):
        """leave from this guild"""
        return await self.gate.exec_req(api.Guild.leave(guild_id=self.id))

    async def get_mute_list(self, return_type: str = 'detail'):
        """get mute list from this guild"""
        return await self.gate.exec_req(api.GuildMute.list(guild_id=self.id, return_type=return_type))

    async def mute(self, user: Union[User, str], type: GuildMuteTypes):
        """create mute on this guild"""
        user_id = user.id if isinstance(user, User) else user
        return await self.gate.exec_req(api.GuildMute.create(guild_id=self.id, user_id=user_id, type=type.value))

    async def unmute(self, user: Union[User, str], type: GuildMuteTypes):
        """delete mute from this guild"""
        user_id = user.id if isinstance(user, User) else user
        return await self.gate.exec_req(api.GuildMute.delete(guild_id=self.id, user_id=user_id, type=type.value))

    async def get_blacklist(self):
        """get blacklist from this guild"""
        return await self.gate.exec_req(api.Blacklist.list(guild_id=self.id))

    async def ban(self, user: Union[User, str], remark: str = None, del_msg_days: int = 0):
        """ban user on this guild"""
        target_id = user.id if isinstance(user, User) else user
        return await self.gate.exec_req(
            api.Blacklist.create(guild_id=self.id, target_id=target_id, remark=remark, del_msg_days=del_msg_days))

    async def unban(self, user: Union[User, str]):
        """unban user on this guild"""
        target_id = user.id if isinstance(user, User) else user
        return await self.gate.exec_req(api.Blacklist.delete(guild_id=self.id, target_id=target_id))

    async def get_badge(self, style: int = 0):
        """get badge from this guild"""
        return await self.gate.exec_req(api.Badge.guild(guild_id=self.id, style=style))

    async def fetch_emojis(self, page: int = None, page_size: int = None):
        return await self.gate.exec_req(api.GuildEmoji.list(guild_id=self.id, page=page, page_size=page_size))

    async def create_emoji(self, name: str, emoji: str):
        return await self.gate.exec_req(api.GuildEmoji.create(guild_id=self.id, name=name, emoji=open(emoji, 'rb')))

    async def update_emoji(self, name: str, id: str):
        return await self.gate.exec_req(api.GuildEmoji.update(name=name, id=id))

    async def delete_emoji(self, id: str):
        return await self.gate.exec_req(api.GuildEmoji.delete(id=id))

    async def list_invite(self, page: int = None, page_size: int = None):
        return await self.gate.exec_req(api.Invite.list(guild_id=self.id, page=page, page_size=page_size))

    async def creat_invite(self,
                           duration: InviteDurationTypes = InviteDurationTypes.SEVEN_DAYS,
                           setting_times: InviteSettingTimesTypes = InviteSettingTimesTypes.UNLIMITED):
        return await self.gate.exec_req(
            api.Invite.create(guild_id=self.id, duration=duration.value, setting_times=setting_times.value))

    async def delete_invite(self, url_code: str):
        return await self.gate.exec_req(api.Invite.delete(guild_id=self.id, url_code=url_code))
