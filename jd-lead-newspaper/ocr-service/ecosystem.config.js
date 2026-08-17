module.exports = {
  apps: [
    {
      name: 'ocr-service',
      script: 'gunicorn',
      args: '--bind 172.21.0.1:5050 --workers 2 --timeout 60 app:app',
      cwd: '/root/projects/lead-manger/jd-lead-newspaper/ocr-service',
      interpreter: 'none',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PYTHONUNBUFFERED: '1',
        OMP_THREAD_LIMIT: '1',
      },
    },
  ],
};
