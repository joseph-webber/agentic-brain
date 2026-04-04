# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Agentic Brain Contributors
#
# Homebrew Cask formula for BrainChat
# Install: brew install --cask brainchat

cask "brainchat" do
  version "1.2.0"
  sha256 "8470ad3f5f6ddda7f9e1a8d9c8f9d7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0"

  url "https://github.com/getagentic/brain/releases/download/v#{version}/BrainChat-#{version}.dmg"
  homepage "https://github.com/getagentic/brain"
  
  desc "🧠 AI Chat Application with Multi-LLM Support and Voice"
  
  livecheck do
    url "https://github.com/getagentic/brain/releases.atom"
    regex(%r{BrainChat[._-]v?(\d+(?:\.\d+)*).dmg}i)
    strategy :github_latest
  end

  app "Brain Chat.app"

  zap trash: [
    "~/Library/Application Support/com.brainchat.app",
    "~/Library/Caches/com.brainchat.app",
    "~/Library/Preferences/com.brainchat.app.plist",
    "~/Library/Saved Application State/com.brainchat.app.savedState",
    "~/Library/Cookies/com.brainchat.app.binarycookies",
  ]
end
