"use client";

import { useState } from "react";
import UnfollowCard from "./UnfollowCard";

interface NonFollower {
  username: string;
  followers: number;
  profile_pic_url: string | null;
  is_verified: boolean;
}

interface Props {
  nonFollowers: NonFollower[];
  /** If undefined, export mode — shows "Open profile" instead of unfollow button */
  onUnfollow?: (username: string) => Promise<boolean>;
}

export default function NonFollowerList({ nonFollowers, onUnfollow }: Props) {
  const [list, setList] = useState(nonFollowers);
  const [unfollowing, setUnfollowing] = useState<string | null>(null);

  async function handleUnfollow(username: string) {
    if (!onUnfollow) return;
    setUnfollowing(username);
    const ok = await onUnfollow(username);
    setUnfollowing(null);
    if (ok) setList((prev) => prev.filter((u) => u.username !== username));
  }

  if (list.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow p-8 text-center">
        <p className="text-2xl">🎉</p>
        <p className="mt-2 font-semibold text-gray-800">
          Todos que você segue seguem você de volta!
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {list.length} conta{list.length !== 1 ? "s" : ""} não seguem você de volta
        </p>
        {onUnfollow && (
          <p className="text-xs text-gray-400">4–8s de intervalo por segurança</p>
        )}
      </div>
      {list.map((u) => (
        <UnfollowCard
          key={u.username}
          username={u.username}
          followers={u.followers}
          profilePicUrl={u.profile_pic_url}
          isVerified={u.is_verified}
          isUnfollowing={unfollowing === u.username}
          onUnfollow={onUnfollow ? () => handleUnfollow(u.username) : undefined}
        />
      ))}
    </div>
  );
}
