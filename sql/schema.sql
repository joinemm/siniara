CREATE TABLE twitter_user (
    user_id BIGINT,
    username VARCHAR(15),
    PRIMARY KEY (user_id)
);

CREATE TABLE guild (
    guild_id BIGINT,
    follow_limit INT,
    PRIMARY KEY (guild_id)
);

CREATE TABLE follow (
    channel_id BIGINT,
    guild_id BIGINT NOT NULL,
    twitter_user_id BIGINT,
    added_on DATETIME,
    PRIMARY KEY (channel_id, twitter_user_id),
    FOREIGN KEY (twitter_user_id) REFERENCES twitter_user (user_id)
);

CREATE TABLE guild_settings (
    guild_id BIGINT,
    media_only BOOL,
    PRIMARY KEY (guild_id)
);

CREATE TABLE channel_settings (
    channel_id BIGINT,
    guild_id BIGINT NOT NULL,
    media_only BOOL,
    PRIMARY KEY (channel_id)
);

CREATE TABLE user_settings (
    guild_id BIGINT,
    twitter_user_id BIGINT,
    media_only BOOL,
    PRIMARY KEY (guild_id, twitter_user_id),
    FOREIGN KEY (twitter_user_id) REFERENCES twitter_user (user_id)
);