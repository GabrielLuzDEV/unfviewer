"use client";

interface Props {
  username: string;
  followers: number;
  profilePicUrl: string | null;
  isVerified: boolean;
  isUnfollowing: boolean;
  /** If undefined, export mode — renders an "Open profile" link instead */
  onUnfollow?: () => void;
}

export default function UnfollowCard({
  username,
  followers,
  profilePicUrl,
  isVerified,
  isUnfollowing,
  onUnfollow,
}: Props) {
  const followersStr =
    followers > 0
      ? followers >= 1_000_000
        ? `${(followers / 1_000_000).toFixed(1)}M`
        : followers >= 1_000
        ? `${(followers / 1_000).toFixed(1)}k`
        : String(followers)
      : null;

  return (
    <div className="flex items-center justify-between bg-white rounded-xl shadow-sm px-4 py-3 hover:shadow transition">
      <div className="flex items-center gap-3">
        {profilePicUrl && /^https:\/\//i.test(profilePicUrl) ? (
          <img
            src={profilePicUrl}
            alt={username}
            className="w-10 h-10 rounded-full object-cover"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white font-bold text-sm">
            {username[0]?.toUpperCase()}
          </div>
        )}
        <div>
          <div className="flex items-center gap-1">
            <a
              href={`https://www.instagram.com/${username}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-gray-900 hover:text-purple-600 transition"
            >
              @{username}
            </a>
            {isVerified && <span className="text-blue-500 text-xs">✓</span>}
          </div>
          {followersStr && (
            <p className="text-xs text-gray-400">{followersStr} seguidores</p>
          )}
        </div>
      </div>

      {onUnfollow ? (
        <button
          onClick={onUnfollow}
          disabled={isUnfollowing}
          className="text-sm font-medium text-red-500 hover:text-red-700 disabled:text-red-300 transition min-w-[7rem] text-right"
        >
          {isUnfollowing ? "Aguardando..." : "Deixar de seguir"}
        </button>
      ) : (
        <a
          href={`https://www.instagram.com/${username}/`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-purple-500 hover:text-purple-700 transition"
        >
          Ver perfil
        </a>
      )}
    </div>
  );
}
