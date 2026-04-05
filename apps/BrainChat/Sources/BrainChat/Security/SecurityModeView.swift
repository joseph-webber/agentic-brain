import SwiftUI

@MainActor
struct SecurityModeView: View {
    @ObservedObject private var securityManager: SecurityManager
    @State private var pendingRole: SecurityRole?
    @State private var showingRestrictionConfirmation = false

    init(securityManager: SecurityManager? = nil) {
        _securityManager = ObservedObject(wrappedValue: securityManager ?? .shared)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 8) {
                Label("Current Mode: \(securityManager.currentRole.accessibilityName)", systemImage: securityManager.currentRole.iconName)
                    .font(.headline)
                    .foregroundStyle(roleColor(securityManager.currentRole))

                Text(securityManager.currentRole.description)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(roleColor(securityManager.currentRole).opacity(0.12))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(roleColor(securityManager.currentRole).opacity(0.35), lineWidth: 1)
            )
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Current security mode: \(securityManager.currentRole.accessibilityName). \(securityManager.currentRole.description)")

            Text("Testing only. Full Admin is the normal operating mode.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Testing only. Full Admin is the normal operating mode.")

            Picker(
                "Security Mode",
                selection: Binding(
                    get: { securityManager.currentRole },
                    set: { requestRoleChange(to: $0) }
                )
            ) {
                ForEach(SecurityRole.allCases, id: \.self) { role in
                    Text(role.displayName).tag(role)
                }
            }
            .pickerStyle(.radioGroup)
            .accessibilityLabel("Security mode picker")
            .accessibilityHint("Choose Full Admin, Safe Admin, User, or Guest testing mode")

            VStack(alignment: .leading, spacing: 8) {
                ForEach(SecurityRole.allCases, id: \.self) { role in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: role.iconName)
                            .foregroundStyle(roleColor(role))
                            .frame(width: 18)
                            .accessibilityHidden(true)

                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(role.accessibilityName)
                                    .font(.subheadline.weight(.semibold))
                                if role == securityManager.currentRole {
                                    Text("Current")
                                        .font(.caption.weight(.semibold))
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(roleColor(role).opacity(0.18))
                                        .clipShape(Capsule())
                                }
                            }

                            Text(role.description)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 2)
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("\(role.accessibilityName). \(role.description)\(role == securityManager.currentRole ? ". Current mode." : "")")
                }
            }
        }
        .confirmationDialog(
            pendingRole.map { "Switch to \($0.accessibilityName) mode?" } ?? "Switch security mode?",
            isPresented: $showingRestrictionConfirmation,
            titleVisibility: .visible
        ) {
            if let pendingRole {
                Button("Switch to \(pendingRole.accessibilityName)", role: .destructive) {
                    securityManager.switchRole(to: pendingRole)
                    self.pendingRole = nil
                }
            }
            Button("Cancel", role: .cancel) {
                pendingRole = nil
            }
        } message: {
            if let pendingRole {
                Text("This testing change reduces Brain Chat permissions. \(pendingRole.description)")
            }
        }
    }

    private func requestRoleChange(to role: SecurityRole) {
        guard role != securityManager.currentRole else { return }

        if securityManager.requiresRestrictionConfirmation(for: role) {
            pendingRole = role
            showingRestrictionConfirmation = true
            return
        }

        securityManager.switchRole(to: role)
    }

    private func roleColor(_ role: SecurityRole) -> Color {
        switch role {
        case .fullAdmin: return .red
        case .safeAdmin: return .green
        case .user: return .orange
        case .guest: return .blue
        }
    }
}
