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
    FOREIGN KEY (twitter_user_id) REFERENCES twitter_user (user_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE guild_settings (
    guild_id BIGINT,
    media_only BOOL,
    PRIMARY KEY (guild_id)
);

CREATE TABLE channel_rule (
    rule_id INT NOT NULL AUTO_INCREMENT,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT,
    media_only BOOL,
    PRIMARY KEY (rule_id),
    UNIQUE (channel_id)
);

CREATE TABLE user_rule (
    rule_id INT NOT NULL AUTO_INCREMENT,
    guild_id BIGINT,
    twitter_user_id BIGINT,
    media_only BOOL,
    PRIMARY KEY (rule_id),
    UNIQUE (guild_id, twitter_user_id),
    FOREIGN KEY (twitter_user_id) REFERENCES twitter_user (user_id) ON DELETE CASCADE ON UPDATE CASCADE
);