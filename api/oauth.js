<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="1;url=playrifa://oauth?code={{code}}&state={{state}}">
  <title>Redirecionando...</title>
  <style>
    body {
      font-family: sans-serif;
      background-color: #f6f8fa;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      text-align: center;
      color: #333;
    }
    .box {
      max-width: 400px;
      padding: 2rem;
      background: white;
      border-radius: 8px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .loader {
      margin-top: 1.5rem;
      border: 4px solid #f3f3f3;
      border-top: 4px solid #3498db;
      border-radius: 50%;
      width: 30px;
      height: 30px;
      animation: spin 1s linear infinite;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div class="box">
    <h2>Redirecionando para o aplicativo...</h2>
    <p>Por favor, aguarde um momento.</p>
    <div class="loader"></div>
  </div>
</body>
</html>
