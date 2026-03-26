# Deployment Playbook

1. Enable maintenance mode.
2. Run the full regression tests.
3. Deploy the containers with `kubectl rollout`.
4. Verify monitoring dashboards for at least 15 minutes.

_Reminder_: Always include the accessibility smoke tests before marking the deployment done.
