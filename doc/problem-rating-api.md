# Codeforces API

## Methods

### `blogEntry.comments`

Returns a list of comments to the specified blog entry.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `blogEntryId` (Required) | Id of the blog entry. It can be seen in blog entry URL. For example: `/blog/entry/79` |

**Return value:** A list of [`Comment`](#comment) objects.

**Example:** `https://codeforces.com/api/blogEntry.comments?blogEntryId=79`

### `blogEntry.view`

Returns blog entry.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `blogEntryId` (Required) | Id of the blog entry. It can be seen in blog entry URL. For example: `/blog/entry/79` |

**Return value:** Returns a [`BlogEntry`](#blogentry) object in full version.

**Example:** `https://codeforces.com/api/blogEntry.view?blogEntryId=79`

### `contest.hacks`

Returns list of hacks in the specified contests. Full information about hacks is available only after some time after the contest end. During the contest user can see only own hacks.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `contestId` (Required) | Id of the contest. It is not the round number. It can be seen in contest URL. For example: `/contest/566/status` |
| `asManager` | Boolean. If set to true, the response will contain information available to contest managers. Otherwise, the response will contain only the information available to the participants. You must be a contest manager to use it. |

**Return value:** Returns a list of [`Hack`](#hack) objects.

**Example:** `https://codeforces.com/api/contest.hacks?contestId=566`

### `contest.list`

Returns information about all available contests.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `gym` | Boolean. If true — than gym contests are returned. Otherwide, regular contests are returned. |
| `groupCode` | Group code (e.g., `sfSJn5pz1a`) is used to filter contests. You need to log in with an account that has at least read access to the group. |

**Return value:** Returns a list of [`Contest`](#contest) objects. If this method is called not anonymously, then all available contests for a calling user will be returned too, including mashups and private gyms.

**Example:** `https://codeforces.com/api/contest.list?gym=true`

### `contest.ratingChanges`

Returns rating changes after the contest.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `contestId` (Required) | Id of the contest. It is not the round number. It can be seen in contest URL. For example: `/contest/566/status` |

**Return value:** Returns a list of [`RatingChange`](#ratingchange) objects.

**Example:** `https://codeforces.com/api/contest.ratingChanges?contestId=566`

### `contest.standings`

Returns the description of the contest and the requested part of the standings.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `contestId` (Required) | Id of the contest. It is not the round number. It can be seen in contest URL. For example: `/contest/566/status` |
| `asManager` | Boolean. If set to true, the response will contain information available to contest managers. Otherwise, the response will contain only the information available to the participants. You must be a contest manager to use it. |
| `from` | 1-based index of the standings row to start the ranklist. |
| `count` | Number of standing rows to return. |
| `handles` | Semicolon-separated list of handles. No more than 10000 handles is accepted. |
| `room` | If specified, than only participants from this room will be shown in the result. If not — all the participants will be shown. |
| `showUnofficial` | If true than all participants (virtual, out of competition) are shown. Otherwise, only official contestants are shown. |
| `participantTypes` | Comma-separated list of participant types without spaces. Possible values: `CONTESTANT`, `PRACTICE`, `VIRTUAL`, `MANAGER`, `OUT_OF_COMPETITION`. Only participants with the specified types will be displayed. |

**Return value:** Returns object with three fields: "contest", "problems" and "rows". Field "contest" contains a [`Contest`](#contest) object. Field "problems" contains a list of [`Problem`](#problem) objects. Field "rows" contains a list of [`RanklistRow`](#ranklistrow) objects.

**Example:** `https://codeforces.com/api/contest.standings?contestId=566&from=1&count=5&showUnofficial=true`

### `contest.status`

Returns submissions for specified contest. Optionally can return submissions of specified user.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `contestId` (Required) | Id of the contest. It is not the round number. It can be seen in contest URL. For example: `/contest/566/status` |
| `asManager` | Boolean. If set to true, the response will contain information available to contest managers. Otherwise, the response will contain only the information available to the participants. You must be a contest manager to use it. |
| `handle` | Codeforces user handle. |
| `from` | 1-based index of the first submission to return. |
| `count` | Number of returned submissions. |
| `includeSources` | Specifies whether to include source codes in the output. Available only when using asManager and if the user has manager permissions for the contest. |

**Return value:** Returns a list of [`Submission`](#submission) objects, sorted in decreasing order of submission id.

**Example:** `https://codeforces.com/api/contest.status?contestId=566&from=1&count=10`

### `problemset.problems`

Returns all problems from problemset. Problems can be filtered by tags.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `tags` | Semicilon-separated list of tags. |
| `problemsetName` | Custom problemset's short name, like 'acmsguru' |

**Return value:** Returns two lists. List of [`Problem`](#problem) objects and list of [`ProblemStatistics`](#problemstatistics) objects.

**Example:** `https://codeforces.com/api/problemset.problems?tags=implementation`

### `problemset.recentStatus`

Returns recent submissions.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `count` (Required) | Number of submissions to return. Can be up to 1000. |
| `problemsetName` | Custom problemset's short name, like 'acmsguru' |

**Return value:** Returns a list of [`Submission`](#submission) objects, sorted in decreasing order of submission id.

**Example:** `https://codeforces.com/api/problemset.recentStatus?count=10`

### `recentActions`

Returns recent actions.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `maxCount` (Required) | Number of recent actions to return. Can be up to 100. |

**Return value:** Returns a list of [`RecentAction`](#recentaction) objects.

**Example:** `https://codeforces.com/api/recentActions?maxCount=30`

### `user.blogEntries`

Returns a list of all user's blog entries.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `handle` (Required) | Codeforces user handle. |

**Return value:** A list of [`BlogEntry`](#blogentry) objects in short form.

**Example:** `https://codeforces.com/api/user.blogEntries?handle=Fefer_Ivan`

### `user.friends`

Returns authorized user's friends. Using this method requires authorization.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `onlyOnline` | Boolean. If true — only online friends are returned. Otherwise, all friends are returned. |

**Return value:** Returns a list of strings — users' handles.

**Example:** `https://codeforces.com/api/user.friends?onlyOnline=true`

### `user.info`

Returns information about one or several users.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `handles` (Required) | Semicolon-separated list of handles. No more than 10000 handles is accepted. |
| `checkHistoricHandles` | Boolean, the default value is true. If this flag is enabled, then use the history of handle changes when searching for a user. |

**Return value:** Returns a list of [`User`](#user) objects for requested handles.

**Example:** `https://codeforces.com/api/user.info?handles=DmitriyH;Fefer_Ivan&checkHistoricHandles=false`

### `user.ratedList`

Returns the list users who have participated in at least one rated contest.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `activeOnly` | Boolean. If true then only users, who participated in rated contest during the last month are returned. Otherwise, all users with at least one rated contest are returned. |
| `includeRetired` | Boolean. If true, the method returns all rated users, otherwise the method returns only users, that were online at last month. |
| `contestId` | Id of the contest. It is not the round number. It can be seen in contest URL. For example: `/contest/566/status` |

**Return value:** Returns a list of [`User`](#user) objects, sorted in decreasing order of rating.

**Example:** `https://codeforces.com/api/user.ratedList?activeOnly=true&includeRetired=false`

### `user.rating`

Returns rating history of the specified user.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `handle` (Required) | Codeforces user handle. |

**Return value:** Returns a list of [`RatingChange`](#ratingchange) objects for requested user.

**Example:** `https://codeforces.com/api/user.rating?handle=Fefer_Ivan`

### `user.status`

Returns submissions of specified user.

#### Parameters

| Parameter | Description |
| :--- | :--- |
| `handle` (Required) | Codeforces user handle. |
| `from` | 1-based index of the first submission to return. |
| `count` | Number of returned submissions. |
| `includeSources` | Specifies whether source codes should be included in the output. This option is only available when requested for your own account. |

**Return value:** Returns a list of [`Submission`](#submission) objects, sorted in decreasing order of submission id.

**Example:** `https://codeforces.com/api/user.status?handle=Fefer_Ivan&from=1&count=10`

## Return objects

### `User`

Represents a Codeforces user.

| Field | Description |
| :--- | :--- |
| `handle` | String. Codeforces user handle. |
| `email` | String. Shown only if user allowed to share his contact info. |
| `vkId` | String. User id for VK social network. Shown only if user allowed to share his contact info. |
| `openId` | String. Shown only if user allowed to share his contact info. |
| `firstName` | String. Localized. Can be absent. |
| `lastName` | String. Localized. Can be absent. |
| `country` | String. Localized. Can be absent. |
| `city` | String. Localized. Can be absent. |
| `organization` | String. Localized. Can be absent. |
| `contribution` | Integer. User contribution. |
| `rank` | String. Localized. |
| `rating` | Integer. |
| `maxRank` | String. Localized. |
| `maxRating` | Integer. |
| `lastOnlineTimeSeconds` | Integer. Time, when user was last seen online, in unix format. |
| `registrationTimeSeconds` | Integer. Time, when user was registered, in unix format. |
| `friendOfCount` | Integer. Amount of users who have this user in friends. |
| `avatar` | String. User's avatar URL. |
| `titlePhoto` | String. User's title photo URL. |

### `BlogEntry`

Represents a Codeforces blog entry. May be in either short or full version.

| Field | Description |
| :--- | :--- |
| `id` | Integer. |
| `originalLocale` | String. Original locale of the blog entry. |
| `creationTimeSeconds` | Integer. Time, when blog entry was created, in unix format. |
| `authorHandle` | String. Author user handle. |
| `title` | String. Localized. |
| `content` | String. Localized. Not included in short version. |
| `locale` | String. |
| `modificationTimeSeconds` | Integer. Time, when blog entry has been updated, in unix format. |
| `allowViewHistory` | Boolean. If true, you can view any specific revision of the blog entry. |
| `tags` | String list. |
| `rating` | Integer. |

### `Comment`

Represents a comment.

| Field | Description |
| :--- | :--- |
| `id` | Integer. |
| `creationTimeSeconds` | Integer. Time, when comment was created, in unix format. |
| `commentatorHandle` | String. |
| `locale` | String. |
| `text` | String. |
| `parentCommentId` | Integer. Can be absent. |
| `rating` | Integer. |

### `RecentAction`

Represents a recent action.

| Field | Description |
| :--- | :--- |
| `timeSeconds` | Integer. Action time, in unix format. |
| `blogEntry` | [`BlogEntry`](#blogentry) object in short form. Can be absent. |
| `comment` | [`Comment`](#comment) object. Can be absent. |

### `RatingChange`

Represents a participation of user in rated contest.

| Field | Description |
| :--- | :--- |
| `contestId` | Integer. |
| `contestName` | String. Localized. |
| `handle` | String. Codeforces user handle. |
| `rank` | Integer. Place of the user in the contest. This field contains user rank on the moment of rating update. If afterwards rank changes (e.g. someone get disqualified), this field will not be update and will contain old rank. |
| `ratingUpdateTimeSeconds` | Integer. Time, when rating for the contest was update, in unix-format. |
| `oldRating` | Integer. User rating before the contest. |
| `newRating` | Integer. User rating after the contest. |

### `Contest`

Represents a contest on Codeforces.

| Field | Description |
| :--- | :--- |
| `id` | Integer. |
| `name` | String. Localized. |
| `type` | Enum: `CF`, `IOI`, `ICPC`. Scoring system used for the contest. |
| `phase` | Enum: `BEFORE`, `CODING`, `PENDING_SYSTEM_TEST`, `SYSTEM_TEST`, `FINISHED`. |
| `frozen` | Boolean. If true, then the ranklist for the contest is frozen and shows only submissions, created before freeze. |
| `durationSeconds` | Integer. Duration of the contest in seconds. |
| `freezeDurationSeconds` | Integer. Can be absent. The ranklist freeze duration of the contest in seconds if any. |
| `startTimeSeconds` | Integer. Can be absent. Contest start time in unix format. |
| `relativeTimeSeconds` | Integer. Can be absent. Number of seconds, passed after the start of the contest. Can be negative. |
| `preparedBy` | String. Can be absent. Handle of the user, how created the contest. |
| `websiteUrl` | String. Can be absent. URL for contest-related website. |
| `description` | String. Localized. Can be absent. |
| `difficulty` | Integer. Can be absent. From 1 to 5. Larger number means more difficult problems. |
| `kind` | String. Localized. Can be absent. Human-readable type of the contest from the following categories: Official ICPC Contest, Official School Contest, Opencup Contest, School/University/City/Region Championship, Training Camp Contest, Official International Personal Contest, Training Contest. |
| `icpcRegion` | String. Localized. Can be absent. Name of the Region for official ICPC contests. |
| `country` | String. Localized. Can be absent. |
| `city` | String. Localized. Can be absent. |
| `season` | String. Can be absent. |

### `Party`

Represents a party, participating in a contest.

| Field | Description |
| :--- | :--- |
| `contestId` | Integer. Can be absent. Id of the contest, in which party is participating. |
| `members` | List of [`Member`](#member) objects. Members of the party. |
| `participantType` | Enum: `CONTESTANT`, `PRACTICE`, `VIRTUAL`, `MANAGER`, `OUT_OF_COMPETITION`. |
| `teamId` | Integer. Can be absent. If party is a team, then it is a unique team id. Otherwise, this field is absent. |
| `teamName` | String. Localized. Can be absent. If party is a team or ghost, then it is a localized name of the team. Otherwise, it is absent. |
| `ghost` | Boolean. If true then this party is a ghost. It participated in the contest, but not on Codeforces. For example, Andrew Stankevich Contests in Gym has ghosts of the participants from Petrozavodsk Training Camp. |
| `room` | Integer. Can be absent. Room of the party. If absent, then the party has no room. |
| `startTimeSeconds` | Integer. Can be absent. Time, when this party started a contest. |

### `Member`

Represents a member of a party.

| Field | Description |
| :--- | :--- |
| `handle` | String. Codeforces user handle. |
| `name` | String. Can be absent. User's name if available. |

### `Problem`

Represents a problem.

| Field | Description |
| :--- | :--- |
| `contestId` | Integer. Can be absent. Id of the contest, containing the problem. |
| `problemsetName` | String. Can be absent. Short name of the problemset the problem belongs to. |
| `index` | String. Usually, a letter or letter with digit(s) indicating the problem index in a contest. |
| `name` | String. Localized. |
| `type` | Enum: `PROGRAMMING`, `QUESTION`. |
| `points` | Floating point number. Can be absent. Maximum amount of points for the problem. |
| `rating` | Integer. Can be absent. Problem rating (difficulty). |
| `tags` | String list. Problem tags. |

### `ProblemStatistics`

Represents a statistic data about a problem.

| Field | Description |
| :--- | :--- |
| `contestId` | Integer. Can be absent. Id of the contest, containing the problem. |
| `index` | String. Usually, a letter or letter with digit(s) indicating the problem index in a contest. |
| `solvedCount` | Integer. Number of users, who solved the problem. |

### `Submission`

Represents a submission.

| Field | Description |
| :--- | :--- |
| `id` | Integer. |
| `contestId` | Integer. Can be absent. |
| `creationTimeSeconds` | Integer. Time, when submission was created, in unix-format. |
| `relativeTimeSeconds` | Integer. Number of seconds, passed after the start of the contest (or a virtual start for virtual parties), before the submission. |
| `problem` | [`Problem`](#problem) object. |
| `author` | [`Party`](#party) object. |
| `programmingLanguage` | String. |
| `verdict` | Enum: `FAILED`, `OK`, `PARTIAL`, `COMPILATION_ERROR`, `RUNTIME_ERROR`, `WRONG_ANSWER`, `WRONG_ANSWER`, `TIME_LIMIT_EXCEEDED`, `MEMORY_LIMIT_EXCEEDED`, `IDLENESS_LIMIT_EXCEEDED`, `SECURITY_VIOLATED`, `CRASHED`, `INPUT_PREPARATION_CRASHED`, `CHALLENGED`, `SKIPPED`, `TESTING`, `REJECTED`, `SUBMITTED`. Can be absent. |
| `testset` | Enum: `SAMPLES`, `PRETESTS`, `TESTS`, `CHALLENGES`, `TESTS1`, ..., `TESTS10`. Testset used for judging the submission. |
| `passedTestCount` | Integer. Number of passed tests. |
| `timeConsumedMillis` | Integer. Maximum time in milliseconds, consumed by solution for one test. |
| `memoryConsumedBytes` | Integer. Maximum memory in bytes, consumed by solution for one test. |
| `points` | Floating point number. Can be absent. Number of scored points for IOI-like contests. |

### `Hack`

Represents a hack, made during Codeforces Round.

| Field | Description |
| :--- | :--- |
| `id` | Integer. |
| `creationTimeSeconds` | Integer. Hack creation time in unix format. |
| `hacker` | [`Party`](#party) object. |
| `defender` | [`Party`](#party) object. |
| `verdict` | Enum: `HACK_SUCCESSFUL`, `HACK_UNSUCCESSFUL`, `INVALID_INPUT`, `GENERATOR_INCOMPILABLE`, `GENERATOR_CRASHED`, `IGNORED`, `TESTING`, `OTHER`. Can be absent. |
| `problem` | [`Problem`](#problem) object. Hacked problem. |
| `test` | String. Can be absent. |
| `judgeProtocol` | Object with three fields: "manual", "protocol" and "verdict". Field manual can have values "true" and "false". If manual is "true" then test for the hack was entered manually. Fields "protocol" and "verdict" contain human-readable description of judge protocol and hack verdict. Localized. Can be absent. |

### `RanklistRow`

Represents a ranklist row.

| Field | Description |
| :--- | :--- |
| `party` | [`Party`](#party) object. Party that took a corresponding place in the contest. |
| `rank` | Integer. Party place in the contest. |
| `points` | Floating point number. Total amount of points, scored by the party. |
| `penalty` | Integer. Total penalty (in ICPC meaning) of the party. |
| `successfulHackCount` | Integer. |
| `unsuccessfulHackCount` | Integer. |
| `problemResults` | List of [`ProblemResult`](#problemresult) objects. Party results for each problem. Order of the problems is the same as in "problems" field of the returned object. |
| `lastSubmissionTimeSeconds` | Integer. For IOI contests only. Time in seconds from the start of the contest to the last submission that added some points to the total score of the party. Can be absent. |

### `ProblemResult`

Represents a submissions results of a party for a problem.

| Field | Description |
| :--- | :--- |
| `points` | Floating point number. |
| `penalty` | Integer. Penalty (in ICPC meaning) of the party for this problem. Can be absent. |
| `rejectedAttemptCount` | Integer. Number of incorrect submissions. |
| `type` | Enum: `PRELIMINARY`, `FINAL`. If type is `PRELIMINARY` then points can decrease (if, for example, solution will fail during system test). Otherwise, party can only increase points for this problem by submitting better solutions. |
| `bestSubmissionTimeSeconds` | Integer. Number of seconds after the start of the contest before the submission, that brought maximal amount of points for this problem. Can be absent. |
