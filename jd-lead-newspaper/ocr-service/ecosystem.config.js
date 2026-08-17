module.exports = {
  apps: [
    {
      name: 'ocr-service',
      script: 'app.py',
      interpreter: 'python3',
      cwd: '/root/projects/lead-manger/jd-lead-newspaper/ocr-service',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PORT: '5050',
        PYTHONUNBUFFERED: '1',
        OMP_THREAD_LIMIT: '1',
      },
    },
  ],
};
